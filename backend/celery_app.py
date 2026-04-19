"""Celery application — broker and registered task modules."""

from celery import Celery

from backend.core.config import settings

celery_app = Celery(
    "nexus_mail_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


def _register_tasks() -> None:
    """Import task modules so @celery_app.task decorators run."""
    import backend.workers.fetcher  # noqa: F401
    import backend.workers.sender  # noqa: F401


_register_tasks()

app = celery_app
