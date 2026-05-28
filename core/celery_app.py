from celery import Celery

from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "mongodb_monitoring",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["tasks.monitoring"],
)

celery_app.conf.timezone = "UTC"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.beat_schedule = {
    "collect-mongodb-monitor-metrics": {
        "task": "tasks.monitoring.collect_all_metrics",
        "schedule": settings.monitor_interval_seconds,
    },
    "collect-mongodb-storage-stats": {
        "task": "tasks.monitoring.collect_all_storage_stats",
        "schedule": settings.storage_stats_interval_seconds,
    },
}
