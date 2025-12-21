import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Базовые настройки, читаемые из окружения.

    Переменные совпадают с .env.example и используются всеми сервисами.
    """

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "plain")

    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://neft:neft@postgres:5432/neft"
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/2")

    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret")
    access_token_expires_min: int = int(os.getenv("ACCESS_TOKEN_EXPIRES_MIN", "60"))
    refresh_token_expires_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", "15"))
    password_pepper: str = os.getenv("PASSWORD_PEPPER", "dev-pepper")

    # Risk & Rules feature flags
    AI_RISK_ENABLED: bool = os.getenv("AI_RISK_ENABLED", "true").lower() in {"1", "true", "yes"}
    RISK_RULES_SOURCE: str = os.getenv("RISK_RULES_SOURCE", "CODE").upper()
    RISK_EXPERIMENTAL_RULE_SET: str = os.getenv("RISK_EXPERIMENTAL_RULE_SET", "")

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

    # Invoice PDFs / storage
    NEFT_INVOICE_PDF_BUCKET: str = os.getenv("NEFT_INVOICE_PDF_BUCKET", "neft-invoices")
    NEFT_INVOICE_PDF_TEMPLATE_VERSION: int = int(os.getenv("NEFT_INVOICE_PDF_TEMPLATE_VERSION", "1"))
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "minioadmin")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")

    @property
    def redis_dsn(self) -> str:
        """Совместимость с более старым кодом, ожидающим REDIS_DSN."""

        return self.redis_url


def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
