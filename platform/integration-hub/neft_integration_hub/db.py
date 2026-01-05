from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from neft_integration_hub.settings import get_settings

settings = get_settings()

Base = declarative_base()

_engine = None
_SessionLocal = None


def _make_engine():
    return create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    )


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)
    return _SessionLocal


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def init_db() -> None:
    from neft_integration_hub import models  # noqa: F401

    if os.getenv("NEFT_AUTO_CREATE_SCHEMA") == "true":
        Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator:
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["Base", "get_db", "get_engine", "get_sessionmaker", "init_db", "reset_engine", "session_scope"]
