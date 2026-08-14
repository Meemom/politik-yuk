from app.settings import get_settings
from celery import Celery

settings = get_settings()

celery_app = Celery(
    "politik_yuk_workers",
    broker=settings.worker_broker_url,
    backend=settings.worker_result_backend_url,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=settings.worker_job_timeout_seconds,
    task_soft_time_limit=max(settings.worker_job_timeout_seconds - 10, 1),
    worker_prefetch_multiplier=1,
)
