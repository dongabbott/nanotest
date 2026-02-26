"""Celery worker configuration and tasks."""
import platform

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

# Windows does not support the prefork (billiard) pool — use solo instead.
# This avoids the "ValueError: not enough values to unpack" from billiard.
if platform.system() == "Windows":
    celery_app.conf.update(
        worker_pool="solo",
    )

# Task routing — dev mode uses the default queue so a plain `celery worker`
# picks up everything.  Uncomment the routes below for production where you
# run dedicated workers per queue (e.g. `celery -A ... -Q execution`).
#
# celery_app.conf.task_routes = {
#     "app.tasks.execution.*": {"queue": "execution"},
#     "app.tasks.analysis.*": {"queue": "analysis"},
# }
