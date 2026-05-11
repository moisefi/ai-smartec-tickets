"""Celery application factory."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ai_smartec_tickets",
    broker=settings.effective_celery_broker_url,
    backend=settings.effective_celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Madrid",
    enable_utc=True,
)
