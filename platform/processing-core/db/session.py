"""Compatibility re-exports for legacy imports."""

import os

from app.db import Base, SessionLocal, engine, get_engine, get_sessionmaker, reset_engine


def init_db() -> None:
    """
    Опциональная инициализация схемы, если она нужна из кода.
    Обычно миграций alembic достаточно, но пусть будет.
    """

    if os.getenv("NEFT_AUTO_CREATE_SCHEMA") == "true":
        real_engine = get_engine()
        if Base is not None:
            Base.metadata.create_all(bind=real_engine)
