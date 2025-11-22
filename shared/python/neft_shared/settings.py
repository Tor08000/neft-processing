import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Базовые настройки, читаемые из окружения.

    Этот набор переменных используется всеми сервисами монорепозитория и
    совпадает с .env.example.
    """

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "plain")

    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://neft:neftpass@postgres:5432/neft"
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret")
    access_token_expires_min: int = int(os.getenv("ACCESS_TOKEN_EXPIRES_MIN", "60"))
    refresh_token_expires_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", "15"))
    password_pepper: str = os.getenv("PASSWORD_PEPPER", "dev-pepper")


def get_settings() -> Settings:
    return Settings()
