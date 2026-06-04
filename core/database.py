from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import OperationFailure

from core.config import get_settings

_client: MongoClient | None = None
CURRENT_OP_SAMPLES_TTL_INDEX = "current_op_samples_checked_at_ttl"


def get_metadata_client() -> MongoClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(
            settings.metadata_mongo_uri, serverSelectionTimeoutMS=2500
        )
    return _client


def get_metadata_db() -> Database:
    settings = get_settings()
    return get_metadata_client()[settings.metadata_mongo_db]


def _ensure_ttl_index(
    collection: Collection, field_name: str, index_name: str, expire_after_seconds: int
) -> None:
    operation_error: OperationFailure | None = None
    try:
        collection.create_index(
            [(field_name, ASCENDING)],
            name=index_name,
            expireAfterSeconds=expire_after_seconds,
        )
        return
    except OperationFailure as exc:
        operation_error = exc

    for index in collection.list_indexes():
        if index.get("name") != index_name:
            continue
        if index.get("expireAfterSeconds") == expire_after_seconds:
            return
        collection.database.command(
            {
                "collMod": collection.name,
                "index": {
                    "name": index_name,
                    "expireAfterSeconds": expire_after_seconds,
                },
            }
        )
        return
    raise operation_error


def ensure_indexes() -> None:
    settings = get_settings()
    db = get_metadata_db()
    db.monitors.create_index([("name", ASCENDING)], unique=True)
    db.monitor_status.create_index([("monitor_id", ASCENDING)], unique=True)
    db.connection_counts.create_index(
        [("monitor_id", ASCENDING), ("checked_at", DESCENDING)]
    )
    db.current_ops.create_index([("monitor_id", ASCENDING), ("checked_at", DESCENDING)])
    _ensure_ttl_index(
        db.current_op_samples,
        "checked_at",
        CURRENT_OP_SAMPLES_TTL_INDEX,
        settings.current_op_samples_ttl_seconds,
    )
    db.server_statuses.create_index(
        [("monitor_id", ASCENDING), ("checked_at", DESCENDING)]
    )
    db.database_stats.create_index(
        [
            ("monitor_id", ASCENDING),
            ("database_name", ASCENDING),
            ("checked_at", DESCENDING),
        ]
    )
    db.collection_stats.create_index(
        [
            ("monitor_id", ASCENDING),
            ("database_name", ASCENDING),
            ("collection_name", ASCENDING),
            ("checked_at", DESCENDING),
        ]
    )


def close_metadata_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
