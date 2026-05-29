from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from bson import ObjectId
from pymongo import DESCENDING

from core.crypto import decrypt_uri, encrypt_uri
from core.database import get_metadata_db
from models.monitor import MonitorCreate, MonitorUpdate, serialize_doc

MONITOR_DATA_COLLECTIONS = (
    "connection_counts",
    "current_ops",
    "server_statuses",
    "database_stats",
    "collection_stats",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _display_uri(uri: str) -> str:
    try:
        parsed = urlsplit(uri)
        host_part = parsed.netloc.rsplit("@", 1)[-1]
        return urlunsplit(
            (parsed.scheme, host_part, parsed.path, parsed.query, parsed.fragment)
        )
    except Exception:
        return uri


def _with_display_uri(monitor: dict[str, Any]) -> dict[str, Any]:
    raw = monitor.pop("uri", None)
    if raw:
        monitor["display_uri"] = _display_uri(decrypt_uri(raw))
    return monitor


def create_monitor(payload: MonitorCreate) -> dict[str, Any]:
    db = get_metadata_db()
    now = _now()
    doc = payload.model_dump()
    doc["uri"] = encrypt_uri(doc["uri"])
    doc["created_at"] = now
    doc["updated_at"] = now
    result = db.monitors.insert_one(doc)
    return get_monitor(str(result.inserted_id)) or {}


def list_monitors() -> list[dict[str, Any]]:
    db = get_metadata_db()
    monitors = []
    for doc in db.monitors.find().sort("name", 1):
        monitor = serialize_doc(doc) or {}
        monitor = _with_display_uri(monitor)
        status = db.monitor_status.find_one({"monitor_id": ObjectId(monitor["id"])})
        monitor["status"] = serialize_doc(status)
        monitor["latest_connection_count"] = serialize_doc(
            db.connection_counts.find_one(
                {"monitor_id": ObjectId(monitor["id"])},
                sort=[("checked_at", DESCENDING)],
            )
        )
        current_ops = (
            serialize_doc(
                db.current_ops.find_one(
                    {"monitor_id": ObjectId(monitor["id"])},
                    sort=[("checked_at", DESCENDING)],
                )
            )
            or {}
        )
        monitor["latest_current_ops"] = {
            "checked_at": current_ops.get("checked_at"),
            "active_count": current_ops.get("active_count", 0),
            "total_count": current_ops.get("total_count", 0),
            "sample_count": len(current_ops.get("sample", [])),
        }
        monitors.append(monitor)
    return monitors


def get_monitor(monitor_id: str) -> dict[str, Any] | None:
    db = get_metadata_db()
    doc = db.monitors.find_one({"_id": ObjectId(monitor_id)})
    monitor = serialize_doc(doc)
    if monitor:
        monitor = _with_display_uri(monitor)
        monitor["status"] = serialize_doc(
            db.monitor_status.find_one({"monitor_id": ObjectId(monitor_id)})
        )
    return monitor


def update_monitor(monitor_id: str, payload: MonitorUpdate) -> dict[str, Any] | None:
    db = get_metadata_db()
    update = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if update:
        if "uri" in update:
            update["uri"] = encrypt_uri(update["uri"])
        update["updated_at"] = _now()
        db.monitors.update_one({"_id": ObjectId(monitor_id)}, {"$set": update})
    return get_monitor(monitor_id)


def delete_monitor(monitor_id: str) -> dict[str, Any] | None:
    db = get_metadata_db()
    monitor = db.monitors.find_one({"_id": ObjectId(monitor_id)}, {"_id": 1})
    if not monitor:
        return None

    deleted_count = db.monitors.delete_one({"_id": ObjectId(monitor_id)}).deleted_count
    if not deleted_count:
        return None

    from tasks.monitoring import delete_monitor_data_task

    task = delete_monitor_data_task.delay(monitor_id)
    return {
        "deleted": True,
        "deleted_counts": {"monitors": deleted_count},
        "cleanup_enqueued": True,
        "cleanup_task_id": task.id,
    }


def latest_metric(collection: str, monitor_id: str) -> dict[str, Any] | None:
    db = get_metadata_db()
    return serialize_doc(
        db[collection].find_one(
            {"monitor_id": ObjectId(monitor_id)}, sort=[("checked_at", DESCENDING)]
        )
    )


def recent_metrics(
    collection: str, monitor_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    db = get_metadata_db()
    return [
        serialize_doc(doc) or {}
        for doc in db[collection]
        .find({"monitor_id": ObjectId(monitor_id)})
        .sort("checked_at", DESCENDING)
        .limit(limit)
    ]


def _recent_chart_rows(
    collection: str, monitor_id: str, fields: dict[str, str]
) -> list[dict[str, Any]]:
    db = get_metadata_db()
    docs = list(
        db[collection]
        .find(
            {"monitor_id": ObjectId(monitor_id)},
            {"checked_at": 1, **{field: 1 for field in fields}},
        )
        .sort("checked_at", DESCENDING)
        .limit(1000)
    )
    rows = []
    for doc in reversed(docs):
        row = {"checked_at": doc.get("checked_at")}
        for output_key, source_key in fields.items():
            value = doc.get(source_key)
            row[output_key] = int(value) if isinstance(value, bool) else value
        rows.append(serialize_doc(row) or {})
    return rows


def _hourly_chart_rows(
    collection: str,
    monitor_id: str,
    days: int,
    averages: dict[str, str],
    sums: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    db = get_metadata_db()
    since = _now() - timedelta(days=days)
    group_values: dict[str, Any] = {"samples": {"$sum": 1}}
    for output_key, source_key in averages.items():
        group_values[output_key] = {"$avg": f"${source_key}"}
    for output_key, source_key in (sums or {}).items():
        group_values[output_key] = {
            "$sum": f"${source_key}" if isinstance(source_key, str) else source_key
        }

    pipeline = [
        {"$match": {"monitor_id": ObjectId(monitor_id), "checked_at": {"$gte": since}}},
        {
            "$group": {
                "_id": {
                    "$dateTrunc": {
                        "date": "$checked_at",
                        "unit": "hour",
                        "timezone": "UTC",
                    }
                },
                **group_values,
            }
        },
        {"$sort": {"_id": 1}},
    ]
    rows = []
    for doc in db[collection].aggregate(pipeline):
        row = {"checked_at": doc["_id"], "samples": doc.get("samples", 0)}
        for output_key in averages:
            value = doc.get(output_key)
            row[output_key] = (
                round(value, 2) if isinstance(value, (int, float)) else value
            )
        for output_key in sums or {}:
            row[output_key] = doc.get(output_key, 0)
        rows.append(serialize_doc(row) or {})
    return rows


def chart_metrics(monitor_id: str, window: str = "last_1000") -> dict[str, Any]:
    windows = {
        "last_1000": None,
        "30d": 30,
        "90d": 90,
        "180d": 180,
        "365d": 365,
    }
    if window not in windows:
        window = "last_1000"

    days = windows[window]
    if days is None:
        return {
            "window": window,
            "bucket": "sample",
            "connections": _recent_chart_rows(
                "connection_counts",
                monitor_id,
                {
                    "current": "current",
                    "available": "available",
                    "total_created": "total_created",
                    "active": "active",
                    "rejected": "rejected",
                },
            ),
            "current_ops": _recent_chart_rows(
                "current_ops",
                monitor_id,
                {"active_count": "active_count", "total_count": "total_count"},
            ),
            "server_checks": _recent_chart_rows(
                "server_statuses",
                monitor_id,
                {"latency_ms": "latency_ms", "ok": "ok"},
            ),
        }

    return {
        "window": window,
        "bucket": "hour",
        "connections": _hourly_chart_rows(
            "connection_counts",
            monitor_id,
            days,
            {
                "current": "current",
                "available": "available",
                "total_created": "total_created",
                "active": "active",
                "rejected": "rejected",
            },
        ),
        "current_ops": _hourly_chart_rows(
            "current_ops",
            monitor_id,
            days,
            {"active_count": "active_count", "total_count": "total_count"},
        ),
        "server_checks": _hourly_chart_rows(
            "server_statuses",
            monitor_id,
            days,
            {"latency_ms": "latency_ms"},
            {"ok_count": {"$cond": ["$ok", 1, 0]}},
        ),
    }


def latest_database_stats(monitor_id: str) -> list[dict[str, Any]]:
    db = get_metadata_db()
    pipeline = [
        {"$match": {"monitor_id": ObjectId(monitor_id)}},
        {"$sort": {"checked_at": DESCENDING}},
        {"$group": {"_id": "$database_name", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"database_name": 1}},
    ]
    return [serialize_doc(doc) or {} for doc in db.database_stats.aggregate(pipeline)]


def latest_collection_stats(
    monitor_id: str, database_name: str | None = None
) -> list[dict[str, Any]]:
    db = get_metadata_db()
    match: dict[str, Any] = {"monitor_id": ObjectId(monitor_id)}
    if database_name:
        match["database_name"] = database_name
    pipeline = [
        {"$match": match},
        {"$sort": {"checked_at": DESCENDING}},
        {
            "$group": {
                "_id": {
                    "database_name": "$database_name",
                    "collection_name": "$collection_name",
                },
                "doc": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"database_name": 1, "collection_name": 1}},
    ]
    return [serialize_doc(doc) or {} for doc in db.collection_stats.aggregate(pipeline)]


def _nested(doc: dict[str, Any], *keys: str) -> Any:
    value: Any = doc
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def latest_current_ops_rows(monitor_id: str) -> dict[str, Any]:
    doc = latest_metric("current_ops", monitor_id)
    if not doc:
        return {"checked_at": None, "active_count": 0, "total_count": 0, "rows": []}

    rows = []
    for op in doc.get("sample", []):
        command = op.get("command") if isinstance(op.get("command"), dict) else {}
        users = op.get("effectiveUsers") or []
        user_names = [
            f"{user.get('user')}@{user.get('db')}"
            for user in users
            if isinstance(user, dict) and user.get("user")
        ]
        rows.append(
            {
                "opid": str(op.get("opid") or ""),
                "client": op.get("client") or "",
                "connection_id": op.get("connectionId") or "",
                "app_name": _nested(op, "clientMetadata", "application", "name") or "",
                "driver": " ".join(
                    part
                    for part in [
                        _nested(op, "clientMetadata", "driver", "name"),
                        _nested(op, "clientMetadata", "driver", "version"),
                    ]
                    if part
                ),
                "platform": _nested(op, "clientMetadata", "platform") or "",
                "user": ", ".join(user_names),
                "namespace": op.get("ns") or "",
                "operation": op.get("op") or "",
                "command": ", ".join(command.keys()) if command else "",
                "secs_running": op.get("secs_running")
                or op.get("microsecs_running", 0) / 1_000_000,
                "active": op.get("active"),
                "waiting_for_lock": op.get("waitingForLock"),
                "desc": op.get("desc") or "",
            }
        )

    return {
        "checked_at": doc.get("checked_at"),
        "active_count": doc.get("active_count", 0),
        "total_count": doc.get("total_count", 0),
        "rows": rows,
    }


def collection_storage_trend(
    monitor_id: str,
    database_name: str,
    collection_name: str,
    window: str = "last_1000",
) -> dict[str, Any]:
    windows = {
        "last_1000": None,
        "30d": 30,
        "90d": 90,
        "180d": 180,
        "365d": 365,
    }
    if window not in windows:
        window = "last_1000"

    db = get_metadata_db()
    match = {
        "monitor_id": ObjectId(monitor_id),
        "database_name": database_name,
        "collection_name": collection_name,
        "ok": True,
    }
    days = windows[window]
    if days is None:
        docs = list(
            db.collection_stats.find(match).sort("checked_at", DESCENDING).limit(1000)
        )
        rows = []
        for doc in reversed(docs):
            rows.append(
                serialize_doc(
                    {
                        "checked_at": doc.get("checked_at"),
                        "count": doc.get("count", 0),
                        "size_bytes": doc.get("size_bytes", 0),
                        "storage_size_bytes": doc.get("storage_size_bytes", 0),
                        "total_index_size_bytes": doc.get("total_index_size_bytes", 0),
                    }
                )
                or {}
            )
        return {"window": window, "bucket": "sample", "rows": rows}

    match["checked_at"] = {"$gte": _now() - timedelta(days=days)}
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "$dateTrunc": {
                        "date": "$checked_at",
                        "unit": "hour",
                        "timezone": "UTC",
                    }
                },
                "samples": {"$sum": 1},
                "count": {"$avg": "$count"},
                "size_bytes": {"$avg": "$size_bytes"},
                "storage_size_bytes": {"$avg": "$storage_size_bytes"},
                "total_index_size_bytes": {"$avg": "$total_index_size_bytes"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    rows = []
    for doc in db.collection_stats.aggregate(pipeline):
        rows.append(
            serialize_doc(
                {
                    "checked_at": doc["_id"],
                    "samples": doc.get("samples", 0),
                    "count": round(doc.get("count", 0), 2),
                    "size_bytes": round(doc.get("size_bytes", 0), 2),
                    "storage_size_bytes": round(doc.get("storage_size_bytes", 0), 2),
                    "total_index_size_bytes": round(
                        doc.get("total_index_size_bytes", 0), 2
                    ),
                }
            )
            or {}
        )
    return {"window": window, "bucket": "hour", "rows": rows}
