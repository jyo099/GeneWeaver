"""Tests for GeneWeaver background alignment processing."""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.alignment import AlignmentJob
from app.models.database import Base
from app.worker.processor import (
    UnavailableAlignmentProcessor,
)
from app.worker.tasks import (
    AlignmentJobNotFoundError,
    execute_alignment_job,
)


class SuccessfulProcessor:
    """Test processor that completes without generating fake results."""

    async def process(
        self,
        job: AlignmentJob,
        session: AsyncSession,
    ) -> None:
        return None


class FailingProcessor:
    """Test processor that simulates a scientific processing failure."""

    async def process(
        self,
        job: AlignmentJob,
        session: AsyncSession,
    ) -> None:
        raise RuntimeError("Simulated processor failure.")


@pytest.fixture
async def session_factory() -> AsyncGenerator[
    async_sessionmaker[AsyncSession],
    None,
]:
    """Create an isolated in-memory SQLite database."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )

    try:
        yield factory
    finally:
        await engine.dispose()


async def create_pending_job(
    session_factory: async_sessionmaker[AsyncSession],
) -> AlignmentJob:
    """Insert a pending alignment job for testing."""

    job = AlignmentJob(
        id=uuid4(),
        guide_sequence="ACGTACGTACGTACGTACGT",
        pam_type="NGG",
        reference_genome="test-reference",
        reference_dataset_version="test-v1",
        algorithm_name="baseline",
        algorithm_version="0.1.0",
        compute_backend="cpu",
        parameters={},
        status="pending",
        progress=0,
    )

    async with session_factory() as session:
        session.add(job)
        await session.commit()
        await session.refresh(job)

    return job


@pytest.mark.asyncio
async def test_worker_completes_job_with_successful_processor(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A successful processor should complete the job."""

    job = await create_pending_job(session_factory)

    result = await execute_alignment_job(
        job_id=job.id,
        session_factory=session_factory,
        processor=SuccessfulProcessor(),
    )

    assert result["status"] == "completed"

    async with session_factory() as session:
        stored_job = await session.get(AlignmentJob, job.id)

        assert stored_job is not None
        assert stored_job.status == "completed"
        assert stored_job.progress == 100
        assert stored_job.started_at is not None
        assert stored_job.completed_at is not None
        assert stored_job.error_message is None


@pytest.mark.asyncio
async def test_worker_records_processor_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Processor exceptions should be persisted as failed jobs."""

    job = await create_pending_job(session_factory)

    result = await execute_alignment_job(
        job_id=job.id,
        session_factory=session_factory,
        processor=FailingProcessor(),
    )

    assert result["status"] == "failed"
    assert "Simulated processor failure" in result["error"]

    async with session_factory() as session:
        stored_job = await session.get(AlignmentJob, job.id)

        assert stored_job is not None
        assert stored_job.status == "failed"
        assert stored_job.completed_at is not None
        assert "Simulated processor failure" in stored_job.error_message


@pytest.mark.asyncio
async def test_worker_does_not_restart_completed_job(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Duplicate task delivery must not restart a completed job."""

    job = await create_pending_job(session_factory)

    async with session_factory() as session:
        stored_job = await session.get(AlignmentJob, job.id)
        assert stored_job is not None

        stored_job.status = "completed"
        stored_job.progress = 100
        await session.commit()

    result = await execute_alignment_job(
        job_id=job.id,
        session_factory=session_factory,
        processor=FailingProcessor(),
    )

    assert result["status"] == "completed"
    assert "no action" in result["message"]

    async with session_factory() as session:
        stored_job = await session.get(AlignmentJob, job.id)

        assert stored_job is not None
        assert stored_job.status == "completed"
        assert stored_job.progress == 100


@pytest.mark.asyncio
async def test_worker_marks_unavailable_processor_as_failed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The default processor must not fabricate genome-wide results."""

    job = await create_pending_job(session_factory)

    result = await execute_alignment_job(
        job_id=job.id,
        session_factory=session_factory,
        processor=UnavailableAlignmentProcessor(),
    )

    assert result["status"] == "failed"
    assert "Genome-wide alignment is not available yet" in result["error"]

    async with session_factory() as session:
        stored_job = await session.get(AlignmentJob, job.id)

        assert stored_job is not None
        assert stored_job.status == "failed"
        assert "No alignment results were generated" in stored_job.error_message


@pytest.mark.asyncio
async def test_worker_rejects_unknown_job(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Unknown job IDs should raise a clear error."""

    with pytest.raises(AlignmentJobNotFoundError):
        await execute_alignment_job(
            job_id=uuid4(),
            session_factory=session_factory,
            processor=SuccessfulProcessor(),
        )
