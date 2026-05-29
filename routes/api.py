from fastapi import APIRouter, HTTPException

from models.monitor import MonitorCreate, MonitorUpdate
from models.responses import (
    ChartMetricsOut,
    CollectionStatsOut,
    CollectionStorageTrendOut,
    ConnectionCountOut,
    CurrentOpsRowsOut,
    CurrentOpsSummaryOut,
    DatabaseStatsOut,
    DeleteMonitorOut,
    EnqueuedOut,
    HealthOut,
    MonitorOut,
    ServerStatusOut,
)
from services.monitor_service import (
    chart_metrics,
    collection_storage_trend,
    create_monitor,
    delete_monitor,
    get_monitor,
    latest_collection_stats,
    latest_current_ops_rows,
    latest_database_stats,
    latest_metric,
    list_monitors,
    recent_metrics,
    update_monitor,
)
from tasks.monitoring import collect_all_metrics, collect_monitor_snapshot

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health():
    return {"ok": True}


@router.get("/monitors", response_model=list[MonitorOut])
def monitors():
    return list_monitors()


@router.post("/monitors", response_model=MonitorOut, status_code=201)
def add_monitor(payload: MonitorCreate):
    return create_monitor(payload)


@router.get("/monitors/{monitor_id}", response_model=MonitorOut)
def monitor_detail(monitor_id: str):
    monitor = get_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    monitor["latest_connection_count"] = latest_metric("connection_counts", monitor_id)
    current_ops = latest_metric("current_ops", monitor_id) or {}
    monitor["latest_current_ops"] = {
        "checked_at": current_ops.get("checked_at"),
        "active_count": current_ops.get("active_count", 0),
        "total_count": current_ops.get("total_count", 0),
        "sample_count": current_ops.get("total_count", 0),
    }
    return monitor


@router.patch("/monitors/{monitor_id}", response_model=MonitorOut)
def patch_monitor(monitor_id: str, payload: MonitorUpdate):
    monitor = update_monitor(monitor_id, payload)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@router.delete("/monitors/{monitor_id}", response_model=DeleteMonitorOut)
def remove_monitor(monitor_id: str):
    result = delete_monitor(monitor_id)
    if not result:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return result


@router.post("/monitors/{monitor_id}/check", response_model=EnqueuedOut)
def check_now(monitor_id: str):
    if not get_monitor(monitor_id):
        raise HTTPException(status_code=404, detail="Monitor not found")
    collect_monitor_snapshot(monitor_id)
    return {"enqueued": True}


@router.post("/checks", response_model=EnqueuedOut)
def check_all_now():
    collect_all_metrics.delay()
    return {"enqueued": True}


@router.get(
    "/monitors/{monitor_id}/metrics/connection_counts",
    response_model=list[ConnectionCountOut],
)
def metric_history_connections(monitor_id: str, limit: int = 20):
    return recent_metrics("connection_counts", monitor_id, min(limit, 1000))


@router.get(
    "/monitors/{monitor_id}/metrics/current_ops",
    response_model=list[CurrentOpsSummaryOut],
)
def metric_history_current_ops(monitor_id: str, limit: int = 20):
    return recent_metrics("current_ops", monitor_id, min(limit, 1000))


@router.get(
    "/monitors/{monitor_id}/metrics/server_statuses",
    response_model=list[ServerStatusOut],
)
def metric_history_server_statuses(monitor_id: str, limit: int = 20):
    return recent_metrics("server_statuses", monitor_id, min(limit, 1000))


@router.get("/monitors/{monitor_id}/charts", response_model=ChartMetricsOut)
def monitor_charts(monitor_id: str, window: str = "last_1000"):
    if not get_monitor(monitor_id):
        raise HTTPException(status_code=404, detail="Monitor not found")
    return chart_metrics(monitor_id, window)


@router.get(
    "/monitors/{monitor_id}/database-stats", response_model=list[DatabaseStatsOut]
)
def monitor_database_stats(monitor_id: str):
    if not get_monitor(monitor_id):
        raise HTTPException(status_code=404, detail="Monitor not found")
    return latest_database_stats(monitor_id)


@router.get(
    "/monitors/{monitor_id}/collection-stats", response_model=list[CollectionStatsOut]
)
def monitor_collection_stats(monitor_id: str, database_name: str | None = None):
    if not get_monitor(monitor_id):
        raise HTTPException(status_code=404, detail="Monitor not found")
    return latest_collection_stats(monitor_id, database_name)


@router.get(
    "/monitors/{monitor_id}/collection-storage-trend",
    response_model=CollectionStorageTrendOut,
)
def monitor_collection_storage_trend(
    monitor_id: str, database_name: str, collection_name: str, window: str = "last_1000"
):
    if not get_monitor(monitor_id):
        raise HTTPException(status_code=404, detail="Monitor not found")
    return collection_storage_trend(monitor_id, database_name, collection_name, window)


@router.get("/monitors/{monitor_id}/current-ops", response_model=CurrentOpsRowsOut)
def monitor_current_ops(monitor_id: str):
    if not get_monitor(monitor_id):
        raise HTTPException(status_code=404, detail="Monitor not found")
    return latest_current_ops_rows(monitor_id)
