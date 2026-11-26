"""Celery application configuration for GeneWeaver."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "geneweaver",
    broker=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    # Task execution
    task_default_queue="alignment",
    task_default_exchange="alignment",
    task_default_routing_key="alignment",
    task_track_started=True,
    # Do not store potentially large genomic results in Redis.
    task_ignore_result=True,
    result_backend=None,
    # Serialization and message safety
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Task execution limits
    task_soft_time_limit=30 * 60,
    task_time_limit=35 * 60,
    # Time zone
    enable_utc=True,
    # Avoid silently discarding messages when workers restart.
    broker_connection_retry_on_startup=True,
)

__all__ = ["celery_app"]
