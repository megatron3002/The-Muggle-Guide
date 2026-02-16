"""Celery application configuration."""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery = Celery(
    "training_pipeline",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.train"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Scheduled retraining: every Sunday at 2 AM
    beat_schedule={
        "scheduled-retrain": {
            "task": "app.tasks.train.retrain_models",
            "schedule": 604800.0,  # 7 days in seconds
        },
    },
)
