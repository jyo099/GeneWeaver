"""Celery tasks for GeneWeaver alignment processing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from celery.exceptions import Ignore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.models.alignment import AlignmentJob
from app.worker.celery_app import celery_app
from app.worker.processor import (
    AlignmentProcessor,
    get_alignment_processor,
)


class AlignmentJobNotFoundError(RuntimeError):
    """Raised when a requested alignment job does not exist."""


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


async def execute_alignment_job(
    job_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    processor: AlignmentProcessor,
) -> dict[str, Any]:
    """
    Execute one alignment job using an independently supplied session factory.

    This function is separated from the Celery task to make job lifecycle
    behavior independently testable.
    """

    async with session_factory() as session:
        result = await session.execute(
            select(AlignmentJob).where(AlignmentJob.id == job_id).with_for_update()
        )
        job = result.scalar_one_or_none()

        if job is None:
            raise AlignmentJobNotFoundError(f"Alignment job {job_id} does not exist.")

        # Duplicate delivery must not restart completed or terminal jobs.
        if job.status != "pending":
            return {
                "job_id": str(job_id),
                "status": job.status,
                "message": "Job was not pending; no action was taken.",
            }

        job.status = "running"
        job.progress = 0
        job.started_at = utc_now()
        job.completed_at = None
        job.error_message = None
        job.updated_at = utc_now()

        await session.commit()

    try:
        async with session_factory() as session:
            result = await session.execute(
                select(AlignmentJob).where(AlignmentJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if job is None:
                raise AlignmentJobNotFoundError(
                    f"Alignment job {job_id} disappeared during execution."
                )

            await processor.process(job, session)
            await session.flush()

            job.status = "completed"
            job.progress = 100
            job.completed_at = utc_now()
            job.updated_at = utc_now()
            job.error_message = None

            await session.commit()

        return {
            "job_id": str(job_id),
            "status": "completed",
        }

    except Exception as exc:  # noqa: BLE001 - record all task failures
        # Roll back any partial result writes before recording failure.
        async with session_factory() as session:
            result = await session.execute(
                select(AlignmentJob).where(AlignmentJob.id == job_id)
            )
            job = result.scalar_one_or_none()

            if job is not None and job.status == "running":
                job.status = "failed"
                job.error_message = (f"{type(exc).__name__}: {exc}")[:4000]
                job.completed_at = utc_now()
                job.updated_at = utc_now()

                await session.commit()

        return {
            "job_id": str(job_id),
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }


@celery_app.task(
    bind=True,
    name="app.worker.tasks.process_alignment_job",
    ignore_result=True,
)
def process_alignment_job(
    self: Any,
    job_id: str,
) -> dict[str, Any]:
    """
    Celery entry point for alignment processing.

    A fresh async SQLAlchemy engine is created and disposed for each task.
    This avoids sharing async database connections across Celery task
    event loops or worker processes.
    """

    try:
        normalized_job_id = UUID(job_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise Ignore() from exc

    settings = get_settings()

    async def run() -> dict[str, Any]:
        engine = create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_pre_ping=True,
        )

        session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        try:
            processor = get_alignment_processor()

            return await execute_alignment_job(
                job_id=normalized_job_id,
                session_factory=session_factory,
                processor=processor,
            )
        finally:
            await engine.dispose()

    return asyncio.run(run())
