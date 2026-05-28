from datetime import datetime, timezone
from typing import Any

from bson import ObjectId, json_util
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_value(item) for key, item in value.items()}
    try:
        json_util.dumps(value)
        return json_util.loads(json_util.dumps(value))
    except Exception:
        pass
    return value


def serialize_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    data = dict(doc)
    if "_id" in data:
        data["id"] = str(data.pop("_id"))
    return normalize_value(data)


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    uri: str = Field(min_length=1)
    enabled: bool = True
    timeout_ms: int = Field(default=2500, ge=250, le=30000)


class MonitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    uri: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None
    timeout_ms: int | None = Field(default=None, ge=250, le=30000)
