from __future__ import annotations

import os
from logging import getLogger

from sqlalchemy.engine import make_url

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

def _normalize_postgres_driver(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _normalize_postgres_driver(
    os.getenv("CRM_DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./crm.db"))
)
logger = getLogger(__name__)


def _log_database_target() -> None:
    if DATABASE_URL.startswith("sqlite"):
        logger.info("CRM DB target: engine=sqlite db=%s", DATABASE_URL)
        return
    try:
        parsed = make_url(DATABASE_URL)
        logger.info(
            "CRM DB target: host=%s port=%s user=%s db=%s",
            parsed.host,
            parsed.port,
            parsed.username,
            parsed.database,
        )
    except Exception:
        logger.warning("CRM DB target: unable to parse database URL")


_log_database_target()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
