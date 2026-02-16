from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    service_name: str = "integration-hub"
    app_env: str = os.getenv("APP_ENV", "prod").lower()
    use_stub_edo: bool = _env_bool("USE_STUB_EDO", "0")
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

    diadok_mode: str = os.getenv("DIADOK_MODE", "mock")
    diadok_base_url: str = os.getenv("DIADOK_BASE_URL", "https://diadok.example.com")
    diadok_api_token: str = os.getenv("DIADOK_API_TOKEN", "")
    diadok_timeout_seconds: int = int(os.getenv("DIADOK_TIMEOUT_SECONDS", "10"))

    webhook_secret_key: str = os.getenv("INTEGRATION_HUB_WEBHOOK_SECRET_KEY", "change-me")
    webhook_max_attempts: int = int(os.getenv("WEBHOOK_MAX_ATTEMPTS", "10"))
    webhook_request_timeout_seconds: int = int(os.getenv("WEBHOOK_REQUEST_TIMEOUT_SECONDS", "10"))
    webhook_sla_seconds: int = int(os.getenv("WEBHOOK_SLA_SECONDS", "300"))
    webhook_alert_failure_threshold: int = int(os.getenv("WEBHOOK_ALERT_FAILURE_THRESHOLD", "10"))
    webhook_intake_secret: str = os.getenv("WEBHOOK_INTAKE_SECRET", "change-me")
    webhook_allow_unsigned: bool = os.getenv("WEBHOOK_ALLOW_UNSIGNED", "true").lower() == "true"

    edo_stub_delivered_after_seconds: int = int(os.getenv("EDO_STUB_DELIVERED_AFTER_SECONDS", "20"))
    edo_stub_signed_after_seconds: int = int(os.getenv("EDO_STUB_SIGNED_AFTER_SECONDS", "60"))
    internal_token: str = os.getenv("INTEGRATION_HUB_INTERNAL_TOKEN", "")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


__all__ = ["Settings", "get_settings"]
