from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from neft_shared.settings import get_settings

settings = get_settings()

DB_SCHEMA = os.getenv("DB_SCHEMA") or os.getenv("NEFT_DB_SCHEMA") or "public"


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


raw_db_url = os.getenv("DATABASE_URL")

if not raw_db_url:
    raise RuntimeError("DATABASE_URL environment variable is required")

try:
    DATABASE_URL: str = _ensure_psycopg_driver(raw_db_url)
except Exception as exc:  # noqa: BLE001 - explicit startup failure
    raise RuntimeError(
        "Invalid DATABASE_URL provided; expected a PostgreSQL DSN such as "
        "'postgresql+psycopg://user:pass@host:5432/dbname'"
    ) from exc


# База для декларативных моделей
Base = declarative_base()


def _make_engine_kwargs(url: str) -> dict:
    engine_kwargs = dict(
        future=True,
        pool_pre_ping=True,
    )

    if url.startswith("postgresql"):
        engine_kwargs["connect_args"] = {"options": f"-csearch_path={DB_SCHEMA},public"}

    if url.startswith("sqlite"):
        engine_kwargs.update(
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    return engine_kwargs


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Lazy singleton for the core SQLAlchemy engine."""

    global _engine

    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            **_make_engine_kwargs(DATABASE_URL),
        )

    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Lazy singleton for the Session factory."""

    global _SessionLocal

    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            class_=Session,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    return _SessionLocal


def reset_engine() -> None:
    """Dispose of the current engine and sessionmaker cache."""

    global _engine, _SessionLocal

    if _engine is not None:
        _engine.dispose()

    _engine = None
    _SessionLocal = None


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
    engine = get_engine()
    if str(engine.url).startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency для FastAPI: даёт сессию и гарантирует её закрытие."""

    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


class _EngineProxy:
    def __call__(self) -> Engine:
        return get_engine()

    def __getattr__(self, item):  # pragma: no cover - passthrough helper
        return getattr(get_engine(), item)


class _SessionLocalProxy:
    def __call__(self) -> Session:
        return get_sessionmaker()()

    def __getattr__(self, item):  # pragma: no cover - passthrough helper
        return getattr(get_sessionmaker(), item)


# Backward-compatible lazy proxies: avoid engine creation at import-time
engine = _EngineProxy()
SessionLocal = _SessionLocalProxy()
