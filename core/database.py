from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from core.config import get_settings

_client: MongoClient | None = None


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


def ensure_indexes() -> None:
    db = get_metadata_db()
    db.monitors.create_index([("name", ASCENDING)], unique=True)
    db.monitor_status.create_index([("monitor_id", ASCENDING)], unique=True)
    db.connection_counts.create_index(
        [("monitor_id", ASCENDING), ("checked_at", DESCENDING)]
    )
    db.current_ops.create_index([("monitor_id", ASCENDING), ("checked_at", DESCENDING)])
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
