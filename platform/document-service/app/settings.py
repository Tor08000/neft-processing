from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    service_name: str = "document-service"
    service_version: str = os.getenv("DOCUMENT_SERVICE_VERSION", "v0")

    s3_endpoint: str = os.getenv("S3_ENDPOINT", os.getenv("NEFT_S3_ENDPOINT", "http://minio:9000"))
    s3_access_key: str = os.getenv("S3_KEY", os.getenv("NEFT_S3_ACCESS_KEY", "change-me"))
    s3_secret_key: str = os.getenv("S3_SECRET", os.getenv("NEFT_S3_SECRET_KEY", "change-me"))
    s3_region: str = os.getenv("S3_REGION", os.getenv("NEFT_S3_REGION", "us-east-1"))
    s3_bucket_docs: str = os.getenv(
        "S3_BUCKET_DOCS",
        os.getenv("NEFT_S3_BUCKET_DOCUMENTS", os.getenv("NEFT_S3_BUCKET", "neft-documents")),
    )
    provider_x_base_url: str = field(default_factory=lambda: os.getenv("PROVIDER_X_BASE_URL", ""))
    provider_x_sandbox_base_url: str = field(default_factory=lambda: os.getenv("PROVIDER_X_SANDBOX_BASE_URL", ""))
    provider_x_api_key: str = field(default_factory=lambda: os.getenv("PROVIDER_X_API_KEY", ""))
    provider_x_api_secret: str = field(default_factory=lambda: os.getenv("PROVIDER_X_API_SECRET", ""))
    esign_callback_secret: str = field(default_factory=lambda: os.getenv("ESIGN_CALLBACK_SECRET", ""))
    provider_x_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("PROVIDER_X_TIMEOUT_SECONDS", "15")))
    provider_x_mode: str = field(default_factory=lambda: os.getenv("ESIGN_PROVIDER_MODE", os.getenv("PROVIDER_X_MODE", "real")))


def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
