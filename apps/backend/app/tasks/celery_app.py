"""Celery worker configuration and tasks."""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "nanotest_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.execution",
        "app.tasks.analysis",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=86400,  # Results expire after 24 hours
)

# Task routing
celery_app.conf.task_routes = {
    "app.tasks.execution.*": {"queue": "execution"},
    "app.tasks.analysis.*": {"queue": "analysis"},
}
