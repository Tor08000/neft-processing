import os
from dataclasses import dataclass


_MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER")
_MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD")
_DEFAULT_MINIO_USER = _MINIO_ROOT_USER or "change-me"
_DEFAULT_MINIO_PASSWORD = _MINIO_ROOT_PASSWORD or "change-me"


def _resolve_database_url() -> str:
    test_url = os.getenv("DATABASE_URL_TEST")
    if test_url and os.getenv("PYTEST_CURRENT_TEST"):
        return test_url
    return os.getenv("DATABASE_URL", "postgresql+psycopg://neft:neft@postgres:5432/neft")


@dataclass
class Settings:
    """Базовые настройки, читаемые из окружения.

    Переменные совпадают с .env.example и используются всеми сервисами.
    """

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "plain")

    database_url: str = _resolve_database_url()
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/2")

    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret")
    access_token_expires_min: int = int(os.getenv("ACCESS_TOKEN_EXPIRES_MIN", "60"))
    refresh_token_expires_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", "15"))
    password_pepper: str = os.getenv("PASSWORD_PEPPER", "dev-pepper")

    # Risk & Rules feature flags
    AI_RISK_ENABLED: bool = os.getenv("AI_RISK_ENABLED", "true").lower() in {"1", "true", "yes"}
    RISK_RULES_SOURCE: str = os.getenv("RISK_RULES_SOURCE", "CODE").upper()
    RISK_EXPERIMENTAL_RULE_SET: str = os.getenv("RISK_EXPERIMENTAL_RULE_SET", "")

    # Logistics navigator feature flags
    LOGISTICS_NAVIGATOR_PROVIDER: str = os.getenv("LOGISTICS_NAVIGATOR_PROVIDER", "noop")
    LOGISTICS_NAVIGATOR_ENABLED: bool = os.getenv("LOGISTICS_NAVIGATOR_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    LOGISTICS_SERVICE_ENABLED: bool = os.getenv("LOGISTICS_SERVICE_ENABLED", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    LOGISTICS_SERVICE_URL: str = os.getenv("LOGISTICS_SERVICE_URL", "http://logistics-service:8000")
    FLEET_BENCHMARK_USE_TENANT: bool = os.getenv("FLEET_BENCHMARK_USE_TENANT", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    # Audit retention defaults
    AUDIT_EXPORT_RETENTION_DAYS: int = int(os.getenv("AUDIT_EXPORT_RETENTION_DAYS", "180"))
    AUDIT_ATTACHMENT_RETENTION_DAYS: int = int(os.getenv("AUDIT_ATTACHMENT_RETENTION_DAYS", "365"))
    AUDIT_DEBUG_RETENTION_DAYS: int = int(os.getenv("AUDIT_DEBUG_RETENTION_DAYS", "30"))
    AUDIT_CACHE_RETENTION_DAYS: int = int(os.getenv("AUDIT_CACHE_RETENTION_DAYS", "7"))
    AUDIT_SIGNING_MODE: str = os.getenv("AUDIT_SIGNING_MODE", "local")
    AUDIT_SIGNING_REQUIRED: bool = os.getenv("AUDIT_SIGNING_REQUIRED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    AUDIT_SIGNING_ALG: str = os.getenv("AUDIT_SIGNING_ALG", "ed25519")
    AUDIT_SIGNING_KEY_ID: str = os.getenv("AUDIT_SIGNING_KEY_ID", "local-dev-key-v1")
    AUDIT_SIGNING_PRIVATE_KEY_B64: str = os.getenv("AUDIT_SIGNING_PRIVATE_KEY_B64", "")
    AUDIT_SIGNING_PUBLIC_KEYS_JSON: str = os.getenv("AUDIT_SIGNING_PUBLIC_KEYS_JSON", "")
    AUDIT_SIGNING_PUBLIC_KEYS_CACHE_SECONDS: int = int(os.getenv("AUDIT_SIGNING_PUBLIC_KEYS_CACHE_SECONDS", "3600"))
    AWS_REGION: str | None = os.getenv("AWS_REGION")
    AWS_ACCESS_KEY_ID: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_KMS_ENDPOINT: str | None = os.getenv("AWS_KMS_ENDPOINT")
    AWS_KMS_VERIFY_MODE: str = os.getenv("AWS_KMS_VERIFY_MODE", "local")
    VAULT_ADDR: str | None = os.getenv("VAULT_ADDR")
    VAULT_TOKEN: str | None = os.getenv("VAULT_TOKEN")
    VAULT_NAMESPACE: str | None = os.getenv("VAULT_NAMESPACE")
    VAULT_TRANSIT_MOUNT: str = os.getenv("VAULT_TRANSIT_MOUNT", "transit")
    VAULT_TRANSIT_KEY: str | None = os.getenv("VAULT_TRANSIT_KEY")
    VAULT_VERIFY_MODE: str = os.getenv("VAULT_VERIFY_MODE", "vault")

    # Billing & clearing configuration
    NEFT_COMMISSION_RATE: float = float(os.getenv("NEFT_COMMISSION_RATE", "0.01"))
    NEFT_BILLING_TZ: str = os.getenv("NEFT_BILLING_TZ", "UTC")
    NEFT_BILLING_DAILY_ENABLED: bool = os.getenv("NEFT_BILLING_DAILY_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    NEFT_BILLING_FINALIZE_GRACE_HOURS: int = int(os.getenv("NEFT_BILLING_FINALIZE_GRACE_HOURS", "12"))
    NEFT_BILLING_DAILY_AT: str = os.getenv("NEFT_BILLING_DAILY_AT", "01:00")
    NEFT_CLEARING_DAILY_ENABLED: bool = os.getenv(
        "NEFT_CLEARING_DAILY_ENABLED", "true"
    ).lower() in {
        "1",
        "true",
        "yes",
    }
    NEFT_CLEARING_DAILY_AT: str = os.getenv("NEFT_CLEARING_DAILY_AT", "02:00")
    NEFT_INVOICE_MONTHLY_ENABLED: bool = os.getenv(
        "NEFT_INVOICE_MONTHLY_ENABLED", "false"
    ).lower() in {"1", "true", "yes"}
    NEFT_INVOICE_MONTHLY_AT: str = os.getenv("NEFT_INVOICE_MONTHLY_AT", "03:00")

    # Stub providers (local demos)
    BANK_STUB_ENABLED: bool = os.getenv("BANK_STUB_ENABLED", "false").lower() in {"1", "true", "yes"}
    BANK_STUB_IMMEDIATE_SETTLE: bool = os.getenv("BANK_STUB_IMMEDIATE_SETTLE", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    ERP_STUB_ENABLED: bool = os.getenv("ERP_STUB_ENABLED", "false").lower() in {"1", "true", "yes"}
    ERP_STUB_AUTO_ACK: bool = os.getenv("ERP_STUB_AUTO_ACK", "true").lower() in {"1", "true", "yes"}

    # Invoice PDFs / storage
    NEFT_INVOICE_PDF_BUCKET: str = os.getenv("NEFT_INVOICE_PDF_BUCKET", "neft-invoices")
    NEFT_S3_BUCKET_INVOICES: str = os.getenv(
        "NEFT_S3_BUCKET_INVOICES", os.getenv("NEFT_INVOICE_PDF_BUCKET", "neft-invoices")
    )
    NEFT_S3_BUCKET_PAYOUTS: str = os.getenv("NEFT_S3_BUCKET_PAYOUTS", "neft-payouts")
    NEFT_S3_BUCKET_DOCUMENTS: str = os.getenv("NEFT_S3_BUCKET_DOCUMENTS", "neft-documents")
    NEFT_S3_BUCKET_ACCOUNTING_EXPORTS: str = os.getenv(
        "NEFT_S3_BUCKET_ACCOUNTING_EXPORTS", "accounting-exports"
    )
    ACCOUNTING_EXPORT_SLA_GENERATE_MINUTES: int = int(os.getenv("ACCOUNTING_EXPORT_SLA_GENERATE_MINUTES", "10"))
    ACCOUNTING_EXPORT_SLA_CONFIRM_HOURS: int = int(os.getenv("ACCOUNTING_EXPORT_SLA_CONFIRM_HOURS", "48"))
    ACCOUNTING_EXPORT_ALERTING_ENABLED: bool = os.getenv(
        "ACCOUNTING_EXPORT_ALERTING_ENABLED", "false"
    ).lower() in {"1", "true", "yes"}
    ACCOUNTING_EXPORT_ALERTING_TARGETS: str = os.getenv("ACCOUNTING_EXPORT_ALERTING_TARGETS", "")
    NEFT_S3_BUCKET: str = os.getenv("NEFT_S3_BUCKET", "")
    NEFT_S3_ACCESS_KEY: str = os.getenv(
        "NEFT_S3_ACCESS_KEY", os.getenv("S3_ACCESS_KEY", _DEFAULT_MINIO_USER)
    )
    NEFT_S3_SECRET_KEY: str = os.getenv(
        "NEFT_S3_SECRET_KEY", os.getenv("S3_SECRET_KEY", _DEFAULT_MINIO_PASSWORD)
    )
    NEFT_S3_ENDPOINT: str = os.getenv("NEFT_S3_ENDPOINT", os.getenv("S3_ENDPOINT_URL", "http://minio:9000"))
    NEFT_S3_REGION: str = os.getenv("NEFT_S3_REGION", os.getenv("S3_REGION", "us-east-1"))
    NEFT_S3_PUBLIC_URL_BASE: str | None = os.getenv("NEFT_S3_PUBLIC_URL_BASE")
    NEFT_INVOICE_PDF_TEMPLATE_VERSION: int = int(os.getenv("NEFT_INVOICE_PDF_TEMPLATE_VERSION", "1"))
    NEFT_PDF_AUTO_GENERATE: bool = os.getenv("NEFT_PDF_AUTO_GENERATE", "0").lower() in {"1", "true", "yes"}
    DOCUMENT_SERVICE_ENABLED: bool = os.getenv("DOCUMENT_SERVICE_ENABLED", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    DOCUMENT_SERVICE_URL: str = os.getenv("DOCUMENT_SERVICE_URL", "http://document-service:8000")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", os.getenv("S3_ENDPOINT_URL", "http://minio:9000"))
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", _DEFAULT_MINIO_USER)
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", _DEFAULT_MINIO_PASSWORD)
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    S3_USE_SSL: bool = os.getenv("S3_USE_SSL", "false").lower() in {"1", "true", "yes"}
    S3_BUCKET_EXPORTS: str = os.getenv("S3_BUCKET_EXPORTS", "case-exports")
    S3_SIGNED_URL_TTL_SECONDS: int = int(os.getenv("S3_SIGNED_URL_TTL_SECONDS", "120"))
    S3_EXPORTS_PREFIX: str = os.getenv("S3_EXPORTS_PREFIX", "exports/")
    S3_OBJECT_LOCK_ENABLED: bool = os.getenv("S3_OBJECT_LOCK_ENABLED", "false").lower() in {"1", "true", "yes"}
    S3_OBJECT_LOCK_MODE: str = os.getenv("S3_OBJECT_LOCK_MODE", "GOVERNANCE")
    S3_OBJECT_LOCK_RETENTION_DAYS: int = int(
        os.getenv("S3_OBJECT_LOCK_RETENTION_DAYS", str(int(os.getenv("AUDIT_EXPORT_RETENTION_DAYS", "180"))))
    )
    S3_OBJECT_LOCK_LEGAL_HOLD: bool = os.getenv("S3_OBJECT_LOCK_LEGAL_HOLD", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    LEGAL_GOST_VERIFY_ENABLED: bool = os.getenv("LEGAL_GOST_VERIFY_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    BI_CLICKHOUSE_ENABLED: bool = os.getenv("BI_CLICKHOUSE_ENABLED", "0").lower() in {"1", "true", "yes"}
    CLICKHOUSE_URL: str = os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123")
    CLICKHOUSE_DB: str = os.getenv("CLICKHOUSE_DB", "default")

    # Telegram notifications
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "")
    TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    TELEGRAM_WEBHOOK_PATH: str = os.getenv("TELEGRAM_WEBHOOK_PATH", "/api/internal/telegram/webhook")
    TELEGRAM_MESSAGE_RATE_LIMIT_PER_MIN: int = int(os.getenv("TELEGRAM_MESSAGE_RATE_LIMIT_PER_MIN", "60"))
    TELEGRAM_MAX_RETRY: int = int(os.getenv("TELEGRAM_MAX_RETRY", "10"))

    # SMS/Voice notifications (stub providers)
    SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "sms_stub")
    VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "voice_stub")
    SMS_STUB_DELIVERY_DELAY_MS: int = int(os.getenv("SMS_STUB_DELIVERY_DELAY_MS", "1000"))
    SMS_STUB_FAIL_RATE: float = float(os.getenv("SMS_STUB_FAIL_RATE", "0.0"))
    VOICE_STUB_DELIVERY_DELAY_MS: int = int(os.getenv("VOICE_STUB_DELIVERY_DELAY_MS", "1000"))
    VOICE_STUB_FAIL_RATE: float = float(os.getenv("VOICE_STUB_FAIL_RATE", "0.0"))

    @property
    def redis_dsn(self) -> str:
        """Совместимость с более старым кодом, ожидающим REDIS_DSN."""

        return self.redis_url


def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
