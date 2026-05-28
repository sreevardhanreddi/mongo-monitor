from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MongoDB Monitoring"
    auth_enabled: bool = False
    auth_username: str = "admin"
    auth_password: str = "admin"

    encryption_key: str = ""

    metadata_mongo_uri: str = "mongodb://metadata-mongodb:27017"
    metadata_mongo_db: str = "mongodb_monitoring"

    redis_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    monitor_interval_seconds: int = Field(default=30, ge=5)
    storage_stats_interval_seconds: int = Field(default=300, ge=60)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
