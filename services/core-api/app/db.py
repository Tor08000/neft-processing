
from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from neft_shared.settings import get_settings

settings = get_settings()

# Read the raw URL from env (preferred NEFT_DB_URL, fallback DATABASE_URL from shared
# settings) and keep a psycopg (v3) default so we don't fall back to psycopg2.
_RAW_DATABASE_URL = os.getenv(
    "NEFT_DB_URL",
    settings.database_url or "postgresql+psycopg://neft:neft@postgres:5432/neft",
)


def _ensure_psycopg_driver(url: str) -> str:
    """Normalize Postgres URLs to use the psycopg v3 driver.

    If the provided URL points to Postgres (with or without an explicit driver),
    force the driver to ``postgresql+psycopg`` so we rely on the installed
    ``psycopg`` package rather than ``psycopg2``. This prevents runtime
    ``ModuleNotFoundError`` when environments provide a URL without a driver
    suffix and SQLAlchemy attempts to import ``psycopg2`` by default.
    """

    sa_url = make_url(url)

    if sa_url.drivername.startswith("postgres"):
        sa_url = sa_url.set(drivername="postgresql+psycopg")

    # Keep credentials intact; ``str(sa_url)`` hides passwords which breaks
    # DSNs that embed them.
    return sa_url.render_as_string(hide_password=False)


DATABASE_URL = _ensure_psycopg_driver(_RAW_DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Создаёт таблицы для декларативных моделей core-api."""

    from app import models  # noqa: F401
    from app.models import Operation  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and guarantee close."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
