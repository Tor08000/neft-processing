from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = "integration-hub"
    service_version: str = os.getenv("INTEGRATION_HUB_VERSION", "v1")

    database_url: str = os.getenv(
        "INTEGRATION_HUB_DATABASE_URL",
        os.getenv("DATABASE_URL", "sqlite:///./integration-hub.db"),
    )

    s3_endpoint: str = os.getenv("S3_ENDPOINT", os.getenv("NEFT_S3_ENDPOINT", "http://minio:9000"))
    s3_access_key: str = os.getenv("S3_KEY", os.getenv("NEFT_S3_ACCESS_KEY", "change-me"))
    s3_secret_key: str = os.getenv("S3_SECRET", os.getenv("NEFT_S3_SECRET_KEY", "change-me"))
    s3_region: str = os.getenv("S3_REGION", os.getenv("NEFT_S3_REGION", "us-east-1"))
    s3_bucket_docs: str = os.getenv(
        "S3_BUCKET_DOCS",
        os.getenv("NEFT_S3_BUCKET_DOCUMENTS", os.getenv("NEFT_S3_BUCKET", "neft-documents")),
    )

    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
    celery_default_queue: str = os.getenv("CELERY_DEFAULT_QUEUE", "edo")
    celery_timezone: str = os.getenv("CELERY_TIMEZONE", "Europe/Moscow")
    celery_enable_utc: bool = os.getenv("CELERY_ENABLE_UTC", "True").lower() == "true"

    edo_max_attempts: int = int(os.getenv("EDO_MAX_ATTEMPTS", "10"))
    edo_poll_interval_seconds: int = int(os.getenv("EDO_POLL_INTERVAL_SECONDS", "30"))


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


__all__ = ["Settings", "get_settings"]
