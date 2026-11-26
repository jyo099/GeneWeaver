"""Tests for the GeneWeaver Celery task dispatcher."""

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.worker.dispatcher import (
    ALIGNMENT_TASK_NAME,
    AlignmentDispatchError,
    enqueue_alignment,
)


def test_dispatcher_submits_job_with_stable_task_id() -> None:
    """The job UUID should also be used as the Celery task ID."""

    job_id = uuid4()

    with patch("app.worker.dispatcher.celery_app.send_task") as send_task:
        task_id = enqueue_alignment(job_id)

    assert task_id == str(job_id)

    send_task.assert_called_once_with(
        ALIGNMENT_TASK_NAME,
        args=[str(job_id)],
        task_id=str(job_id),
        queue="alignment",
    )


def test_dispatcher_accepts_uuid_string() -> None:
    """A valid UUID string should be accepted."""

    job_id = str(uuid4())

    with patch("app.worker.dispatcher.celery_app.send_task"):
        assert enqueue_alignment(job_id) == job_id


@pytest.mark.parametrize(
    "invalid_job_id",
    [
        "",
        "not-a-uuid",
        "12345",
        None,
    ],
)
def test_dispatcher_rejects_invalid_uuid(invalid_job_id: object) -> None:
    """Invalid job identifiers should fail before contacting Redis."""

    with (
        patch("app.worker.dispatcher.celery_app.send_task") as send_task,
        pytest.raises(ValueError, match="valid UUID"),
    ):
        enqueue_alignment(invalid_job_id)

    send_task.assert_not_called()


def test_dispatcher_wraps_broker_errors() -> None:
    """Broker failures should have a clear application-level exception."""

    job_id = uuid4()

    with (
        patch(
            "app.worker.dispatcher.celery_app.send_task",
            side_effect=ConnectionError("Redis unavailable"),
        ),
        pytest.raises(AlignmentDispatchError),
    ):
        enqueue_alignment(job_id)
