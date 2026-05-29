from typing import Any

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ── monitor_status ────────────────────────────────────────────────────────────


class MonitorStatusOut(_Base):
    id: str
    monitor_id: str
    state: str
    latency_ms: float | None = None
    version: str | None = None
    last_error: str | None = None
    checked_at: str | None = None


# ── connection_counts ─────────────────────────────────────────────────────────


class ConnectionCountOut(_Base):
    id: str
    monitor_id: str
    current: int
    available: int
    total_created: int
    active: int
    rejected: int
    checked_at: str


# ── current_ops (header doc, no samples) ─────────────────────────────────────


class CurrentOpsSummaryOut(_Base):
    id: str | None = None
    monitor_id: str | None = None
    active_count: int
    total_count: int
    checked_at: str | None = None


class LatestCurrentOpsSummaryOut(_Base):
    checked_at: str | None = None
    active_count: int
    total_count: int
    sample_count: int


# ── server_statuses ───────────────────────────────────────────────────────────


class ServerStatusOut(_Base):
    id: str
    monitor_id: str
    ok: bool
    latency_ms: float
    version: str | None = None
    uptime_seconds: float | None = None
    host: str | None = None
    error: str | None = None
    checked_at: str


# ── monitors ──────────────────────────────────────────────────────────────────


class MonitorOut(_Base):
    id: str
    name: str
    display_uri: str
    enabled: bool
    timeout_ms: int
    created_at: str
    updated_at: str
    status: MonitorStatusOut | None = None
    latest_connection_count: ConnectionCountOut | None = None
    latest_current_ops: LatestCurrentOpsSummaryOut | None = None


# ── current_ops rows (for /current-ops endpoint) ─────────────────────────────


class CurrentOpRowOut(_Base):
    opid: str
    client: str
    connection_id: str | int
    app_name: str
    driver: str
    platform: str
    os_name: str
    os_version: str
    os_architecture: str
    container_runtime: str
    user: str
    namespace: str
    operation: str
    command: str
    secs_running: float
    active: bool | None = None
    waiting_for_lock: bool | None = None
    desc: str


class CurrentOpsRowsOut(_Base):
    checked_at: str | None = None
    active_count: int
    total_count: int
    rows: list[CurrentOpRowOut]


# ── database_stats ────────────────────────────────────────────────────────────


class DatabaseStatsOut(_Base):
    id: str
    monitor_id: str
    database_name: str
    collections: int
    objects: int
    data_size_bytes: int | float
    storage_size_bytes: int | float
    index_size_bytes: int | float
    total_size_bytes: int | float
    checked_at: str


# ── collection_stats ──────────────────────────────────────────────────────────


class CollectionStatsOut(_Base):
    id: str
    monitor_id: str
    database_name: str
    collection_name: str
    ok: bool
    count: int | None = None
    size_bytes: int | float | None = None
    storage_size_bytes: int | float | None = None
    total_index_size_bytes: int | float | None = None
    avg_obj_size_bytes: int | float | None = None
    nindexes: int | None = None
    error: str | None = None
    checked_at: str


# ── chart schemas ─────────────────────────────────────────────────────────────


class ConnectionChartRowOut(_Base):
    checked_at: str
    current: int | float | None = None
    available: int | float | None = None
    total_created: int | float | None = None
    active: int | float | None = None
    rejected: int | float | None = None
    samples: int | None = None


class CurrentOpsChartRowOut(_Base):
    checked_at: str
    active_count: int | float | None = None
    total_count: int | float | None = None
    samples: int | None = None


class ServerCheckChartRowOut(_Base):
    checked_at: str
    latency_ms: float | None = None
    ok: bool | None = None
    ok_count: int | None = None
    samples: int | None = None


class ChartMetricsOut(_Base):
    window: str
    bucket: str
    connections: list[ConnectionChartRowOut]
    current_ops: list[CurrentOpsChartRowOut]
    server_checks: list[ServerCheckChartRowOut]


# ── collection storage trend ──────────────────────────────────────────────────


class CollectionStorageRowOut(_Base):
    checked_at: str
    count: int | float
    size_bytes: int | float
    storage_size_bytes: int | float
    total_index_size_bytes: int | float
    samples: int | None = None


class CollectionStorageTrendOut(_Base):
    window: str
    bucket: str
    rows: list[CollectionStorageRowOut]


# ── misc ──────────────────────────────────────────────────────────────────────


class DeleteMonitorOut(_Base):
    deleted: bool
    deleted_counts: dict[str, int]
    cleanup_enqueued: bool
    cleanup_task_id: str


class EnqueuedOut(_Base):
    enqueued: bool | int


class HealthOut(_Base):
    ok: bool
