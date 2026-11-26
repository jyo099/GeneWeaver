"""Dispatch alignment jobs to the Celery worker queue."""

from __future__ import annotations

from uuid import UUID

from app.worker.celery_app import celery_app

ALIGNMENT_TASK_NAME = "app.worker.tasks.process_alignment_job"


class AlignmentDispatchError(RuntimeError):
    """Raised when an alignment job cannot be dispatched."""


def enqueue_alignment(job_id: UUID | str) -> str:
    """
    Submit an alignment job to the background queue.

    The alignment job UUID is reused as the Celery task ID. This
    provides a stable identifier across API requests and worker logs.

    Args:
        job_id: Existing GeneWeaver alignment job UUID.

    Returns:
        The Celery task ID.

    Raises:
        ValueError: If the supplied job ID is not a valid UUID.
        AlignmentDispatchError: If the broker rejects the task.
    """

    try:
        normalized_job_id = str(UUID(str(job_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("job_id must be a valid UUID.") from exc

    try:
        celery_app.send_task(
            ALIGNMENT_TASK_NAME,
            args=[normalized_job_id],
            task_id=normalized_job_id,
            queue="alignment",
        )
    except Exception as exc:
        raise AlignmentDispatchError(
            f"Unable to enqueue alignment job {normalized_job_id}."
        ) from exc

    return normalized_job_id
