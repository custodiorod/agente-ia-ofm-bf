from celery import Celery
from app.config import settings

# Create Celery instance
celery_app = Celery(
    "agente_ia_ofm",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.message_tasks",
        "app.tasks.payment_tasks",
        "app.tasks.followup_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.celery_task_time_limit,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


# Configure periodic tasks for follow-ups
celery_app.conf.beat_schedule = {
    "process-pending-followups": {
        "task": "app.tasks.followup_tasks.process_pending_followups",
        "schedule": 60.0,  # Run every 60 seconds
    },
}
