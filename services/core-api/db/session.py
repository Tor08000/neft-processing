# services/core-api/db/session.py

import os

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

# URL БД берём из переменной окружения (как в alembic.ini)
# Если переменной нет — дефолт на твой Postgres в docker-compose
DATABASE_URL = os.getenv(
    "NEFT_DB_URL",
    "postgresql+psycopg2://neft:neft@postgres:5432/neft",
)


def _ensure_psycopg_driver(url: str) -> str:
    """Normalize Postgres URLs to use the psycopg v3 driver."""

    sa_url = make_url(url)

    if sa_url.drivername in {"postgresql", "postgres"} or sa_url.drivername.endswith(
        "+psycopg2"
    ):
        sa_url = sa_url.set(drivername="postgresql+psycopg")

    return str(sa_url)


DATABASE_URL = _ensure_psycopg_driver(DATABASE_URL)

# Создаём engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Фабрика сессий
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# Если хочешь инициализировать таблицы напрямую из кода
try:
    from app.models import Base
except ImportError:
    Base = None


def init_db() -> None:
    """
    Опциональная инициализация схемы, если она нужна из кода.
    Обычно миграций alembic достаточно, но пусть будет.
    """
    if Base is not None:
        Base.metadata.create_all(bind=engine)
