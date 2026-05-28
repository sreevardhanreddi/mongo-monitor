from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from pymongo import MongoClient

from core.crypto import decrypt_uri
from core.database import get_metadata_db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _task_safe(doc: dict[str, Any]) -> dict[str, Any]:
    data = dict(doc)
    data.pop("_id", None)
    if isinstance(data.get("checked_at"), datetime):
        data["checked_at"] = data["checked_at"].isoformat()
    return data


def collect_server_status(monitor: dict[str, Any]) -> dict[str, Any]:
    started = perf_counter()
    checked_at = _now()
    db = get_metadata_db()
    monitor_id = str(monitor["_id"])
    try:
        client = MongoClient(
            decrypt_uri(monitor["uri"]),
            serverSelectionTimeoutMS=monitor.get("timeout_ms", 2500),
        )
        status = client.admin.command("serverStatus")
        latency_ms = round((perf_counter() - started) * 1000, 2)
        doc = {
            "monitor_id": monitor_id,
            "ok": True,
            "latency_ms": latency_ms,
            "version": status.get("version"),
            "uptime_seconds": status.get("uptime"),
            "host": status.get("host"),
            "checked_at": checked_at,
        }
        db.server_statuses.insert_one(doc)
        db.monitor_status.update_one(
            {"monitor_id": monitor_id},
            {
                "$set": {
                    "monitor_id": monitor_id,
                    "state": "up",
                    "latency_ms": latency_ms,
                    "version": status.get("version"),
                    "last_error": None,
                    "checked_at": checked_at,
                }
            },
            upsert=True,
        )
        client.close()
        return {
            "monitor_id": monitor_id,
            "ok": True,
            "latency_ms": latency_ms,
            "checked_at": checked_at.isoformat(),
        }
    except Exception as exc:
        latency_ms = round((perf_counter() - started) * 1000, 2)
        doc = {
            "monitor_id": monitor_id,
            "ok": False,
            "latency_ms": latency_ms,
            "error": str(exc),
            "checked_at": checked_at,
        }
        db.server_statuses.insert_one(doc)
        db.monitor_status.update_one(
            {"monitor_id": monitor_id},
            {
                "$set": {
                    "monitor_id": monitor_id,
                    "state": "down",
                    "latency_ms": latency_ms,
                    "last_error": str(exc),
                    "checked_at": checked_at,
                }
            },
            upsert=True,
        )
        return {
            "monitor_id": monitor_id,
            "ok": False,
            "latency_ms": latency_ms,
            "error": str(exc),
            "checked_at": checked_at.isoformat(),
        }


def collect_connection_count(monitor: dict[str, Any]) -> dict[str, Any]:
    client = MongoClient(
        decrypt_uri(monitor["uri"]),
        serverSelectionTimeoutMS=monitor.get("timeout_ms", 2500),
    )
    status = client.admin.command("serverStatus")
    connections = status.get("connections", {})
    doc = {
        "monitor_id": str(monitor["_id"]),
        "current": connections.get("current", 0),
        "available": connections.get("available", 0),
        "total_created": connections.get("totalCreated", 0),
        "active": connections.get("active", 0),
        "rejected": connections.get("rejected", 0),
        "checked_at": _now(),
    }
    get_metadata_db().connection_counts.insert_one(doc)
    client.close()
    return {
        "monitor_id": doc["monitor_id"],
        "current": doc["current"],
        "available": doc["available"],
        "total_created": doc["total_created"],
        "active": doc["active"],
        "rejected": doc["rejected"],
        "checked_at": doc["checked_at"].isoformat(),
    }


def collect_current_ops(monitor: dict[str, Any]) -> dict[str, Any]:
    client = MongoClient(
        decrypt_uri(monitor["uri"]),
        serverSelectionTimeoutMS=monitor.get("timeout_ms", 2500),
    )
    current_op = client.admin.command("currentOp")
    inprog = current_op.get("inprog", [])
    active_ops = [op for op in inprog if op.get("active")]
    doc = {
        "monitor_id": str(monitor["_id"]),
        "active_count": len(active_ops),
        "total_count": len(inprog),
        "sample": inprog,
        "checked_at": _now(),
    }
    get_metadata_db().current_ops.insert_one(doc)
    client.close()
    return {
        "monitor_id": doc["monitor_id"],
        "active_count": doc["active_count"],
        "total_count": doc["total_count"],
        "sample_count": len(doc["sample"]),
        "checked_at": doc["checked_at"].isoformat(),
    }


def collect_database_and_collection_stats(monitor: dict[str, Any]) -> dict[str, Any]:
    client = MongoClient(
        decrypt_uri(monitor["uri"]),
        serverSelectionTimeoutMS=monitor.get("timeout_ms", 2500),
    )
    metadata_db = get_metadata_db()
    monitor_id = str(monitor["_id"])
    checked_at = _now()
    database_docs = []
    collection_docs = []

    for database_name in client.list_database_names():
        if database_name in {"admin", "config", "local"}:
            continue

        target_db = client[database_name]
        db_stats = target_db.command("dbStats", scale=1)
        collection_names = target_db.list_collection_names()
        database_docs.append(
            {
                "monitor_id": monitor_id,
                "database_name": database_name,
                "collections": db_stats.get("collections", len(collection_names)),
                "objects": db_stats.get("objects", 0),
                "data_size_bytes": db_stats.get("dataSize", 0),
                "storage_size_bytes": db_stats.get("storageSize", 0),
                "index_size_bytes": db_stats.get("indexSize", 0),
                "total_size_bytes": db_stats.get("totalSize", 0),
                "checked_at": checked_at,
            }
        )

        for collection_name in collection_names:
            if collection_name.startswith("system."):
                continue
            try:
                coll_stats = target_db.command("collStats", collection_name, scale=1)
            except Exception as exc:
                collection_docs.append(
                    {
                        "monitor_id": monitor_id,
                        "database_name": database_name,
                        "collection_name": collection_name,
                        "ok": False,
                        "error": str(exc),
                        "checked_at": checked_at,
                    }
                )
                continue
            collection_docs.append(
                {
                    "monitor_id": monitor_id,
                    "database_name": database_name,
                    "collection_name": collection_name,
                    "ok": True,
                    "count": coll_stats.get("count", 0),
                    "size_bytes": coll_stats.get("size", 0),
                    "storage_size_bytes": coll_stats.get("storageSize", 0),
                    "total_index_size_bytes": coll_stats.get("totalIndexSize", 0),
                    "avg_obj_size_bytes": coll_stats.get("avgObjSize", 0),
                    "nindexes": coll_stats.get("nindexes", 0),
                    "checked_at": checked_at,
                }
            )

    if database_docs:
        metadata_db.database_stats.insert_many(database_docs)
    if collection_docs:
        metadata_db.collection_stats.insert_many(collection_docs)
    client.close()
    return {
        "monitor_id": monitor_id,
        "database_count": len(database_docs),
        "collection_count": len(collection_docs),
        "checked_at": checked_at.isoformat(),
    }
