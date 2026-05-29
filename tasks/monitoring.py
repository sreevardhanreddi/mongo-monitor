from bson import ObjectId

from core.celery_app import celery_app
from core.database import get_metadata_db
from services.check_service import (
    collect_connection_count,
    collect_current_ops,
    collect_database_and_collection_stats,
    collect_server_status,
)
from services.monitor_service import MONITOR_DATA_COLLECTIONS


def _monitor_or_none(monitor_id: str):
    return get_metadata_db().monitors.find_one(
        {"_id": ObjectId(monitor_id), "enabled": True}
    )


@celery_app.task(name="tasks.monitoring.collect_server_status")
def collect_server_status_task(monitor_id: str):
    monitor = _monitor_or_none(monitor_id)
    if not monitor:
        return {"skipped": True}
    return collect_server_status(monitor)


@celery_app.task(name="tasks.monitoring.collect_connection_count")
def collect_connection_count_task(monitor_id: str):
    monitor = _monitor_or_none(monitor_id)
    if not monitor:
        return {"skipped": True}
    return collect_connection_count(monitor)


@celery_app.task(name="tasks.monitoring.collect_current_ops")
def collect_current_ops_task(monitor_id: str):
    monitor = _monitor_or_none(monitor_id)
    if not monitor:
        return {"skipped": True}
    return collect_current_ops(monitor)


@celery_app.task(name="tasks.monitoring.collect_storage_stats")
def collect_storage_stats_task(monitor_id: str):
    monitor = _monitor_or_none(monitor_id)
    if not monitor:
        return {"skipped": True}
    return collect_database_and_collection_stats(monitor)


@celery_app.task(name="tasks.monitoring.collect_all_metrics")
def collect_all_metrics():
    monitors = list(get_metadata_db().monitors.find({"enabled": True}))
    for monitor in monitors:
        monitor_id = str(monitor["_id"])
        collect_monitor_snapshot(monitor_id)
    return {"enqueued": len(monitors)}


@celery_app.task(name="tasks.monitoring.collect_all_storage_stats")
def collect_all_storage_stats():
    monitors = list(get_metadata_db().monitors.find({"enabled": True}))
    for monitor in monitors:
        collect_storage_stats_task.delay(str(monitor["_id"]))
    return {"enqueued": len(monitors)}


def collect_monitor_snapshot(monitor_id: str) -> None:
    collect_server_status_task.delay(monitor_id)
    collect_connection_count_task.delay(monitor_id)
    collect_current_ops_task.delay(monitor_id)


@celery_app.task(name="tasks.monitoring.delete_monitor_data")
def delete_monitor_data_task(monitor_id: str):
    db = get_metadata_db()
    deleted_counts = {
        collection: db[collection]
        .delete_many({"monitor_id": ObjectId(monitor_id)})
        .deleted_count
        for collection in MONITOR_DATA_COLLECTIONS
    }
    deleted_counts["monitor_status"] = db.monitor_status.delete_many(
        {"monitor_id": ObjectId(monitor_id)}
    ).deleted_count
    return {"monitor_id": monitor_id, "deleted_counts": deleted_counts}
