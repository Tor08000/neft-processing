from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from neft_shared.settings import get_settings

settings = get_settings()

DB_SCHEMA = os.getenv("DB_SCHEMA", "public")


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


# 1) Берём URL из переменной окружения DATABASE_URL (как в docker-compose/.env)
# 2) Затем пробуем NEFT_DB_URL для обратной совместимости
# 3) Затем настройки (dataclass Settings) — поле database_url
# 4) Если ничего нет — дефолт на локальный Postgres из docker-compose
raw_db_url = (
    os.getenv("DATABASE_URL")
    or os.getenv("NEFT_DB_URL")
    or getattr(settings, "NEFT_DB_URL", None)
    or getattr(settings, "database_url", None)
    or "postgresql+psycopg://neft:neft@postgres:5432/neft"
)

DATABASE_URL: str = _ensure_psycopg_driver(raw_db_url)


# Базовый engine
engine_kwargs = dict(
    future=True,
    pool_pre_ping=True,
)

if DATABASE_URL.startswith("postgresql"):
    engine_kwargs["connect_args"] = {"options": f"-csearch_path={DB_SCHEMA}"}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

engine = create_engine(
    DATABASE_URL,
    **engine_kwargs,
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
    — не создаём таблицы напрямую (используем только Alembic миграции)
    """

    # Импорт нужен только для регистрации моделей, переменные не используются
    from app import models  # noqa: F401
    from app.models.operation import Operation  # noqa: F401
    from app.models.merchant import Merchant  # noqa: F401
    from app.models.terminal import Terminal  # noqa: F401
    from app.models.card import Card  # noqa: F401
    from app.models.partner import Partner  # noqa: F401
    from app.models.limit_rule import LimitRule  # noqa: F401
    from app.models.groups import (  # noqa: F401
        CardGroup,
        CardGroupMember,
        ClientGroup,
        ClientGroupMember,
    )
    from app.models.risk_rule import (  # noqa: F401
        RiskRule,
        RiskRuleAudit,
        RiskRuleVersion,
    )
    from app.models.account import Account, AccountBalance  # noqa: F401
    from app.models.ledger_entry import LedgerEntry  # noqa: F401

    # Для тестов и in-memory SQLite создаём таблицы автоматически.
    if str(engine.url).startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency для FastAPI: даёт сессию и гарантирует её закрытие."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
