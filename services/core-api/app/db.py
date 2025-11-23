from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from neft_shared.settings import get_settings

settings = get_settings()


def _ensure_psycopg_driver(url: str) -> str:
    """
    Нормализуем Postgres-URL так, чтобы всегда использовать драйвер psycopg v3.

    ВАЖНО: render_as_string(hide_password=False), иначе SQLAlchemy замаскирует
    пароль как "***" и коннект всегда будет падать по auth failed.
    """
    sa_url = make_url(url)

    if sa_url.drivername in {"postgres", "postgresql"} or sa_url.drivername.endswith(
        "+psycopg2"
    ):
        sa_url = sa_url.set(drivername="postgresql+psycopg")

    # не прячем пароль!
    return sa_url.render_as_string(hide_password=False)


# 1) Берём URL из переменной окружения NEFT_DB_URL (как в alembic.ini)
# 2) Если её нет — пробуем достать из settings.NEFT_DB_URL
# 3) Если и там нет — дефолт на локальный Postgres из docker-compose
raw_db_url = (
    os.getenv("NEFT_DB_URL")
    or getattr(settings, "NEFT_DB_URL", None)
    or "postgresql+psycopg://neft:neft@postgres:5432/neft"
)

DATABASE_URL: str = _ensure_psycopg_driver(raw_db_url)


# Базовый engine
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
)

# База для декларативных моделей
Base = declarative_base()

# Фабрика сессий
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """
    Инициализация БД при старте приложения:
    — импортируем все модели, чтобы они зарегистрировались в Base.metadata
    — создаём таблицы (для dev/локалки)
    """

    # Импорт нужен только для регистрации моделей, переменные не используются
    from app import models  # noqa: F401
    from app.models.operation import Operation  # noqa: F401
    # TODO: когда появятся другие модели (Client, Card, Transaction и т.п.),
    # добавить их импорт сюда по аналогии, либо обеспечить их импорт в app.models.

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency для FastAPI: даёт сессию и гарантирует её закрытие."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
