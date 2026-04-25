from __future__ import annotations

from typing import Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from neft_integration_hub.db import Base
from neft_integration_hub.models import (
    EdoDocument,
    EdoStubDocument,
    EdoStubEvent,
    WebhookAlert,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookIntakeEvent,
    WebhookReplay,
    WebhookSubscription,
)

EDO_TABLES = [
    EdoDocument.__table__,
    EdoStubDocument.__table__,
    EdoStubEvent.__table__,
]

WEBHOOK_TABLES = [
    WebhookEndpoint.__table__,
    WebhookSubscription.__table__,
    WebhookDelivery.__table__,
    WebhookReplay.__table__,
    WebhookAlert.__table__,
]

WEBHOOK_INTAKE_TABLES = [WebhookIntakeEvent.__table__]


def _create_sessionmaker(
    tables: Iterable,
    *,
    static_pool: bool = False,
) -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite:///:memory:" if not static_pool else "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool if static_pool else None,
    )
    Base.metadata.create_all(bind=engine, tables=list(tables))
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def make_sqlite_session(*tables) -> Session:
    return _create_sessionmaker(tables or Base.metadata.sorted_tables)()


def make_sqlite_session_factory(*tables, static_pool: bool = False) -> sessionmaker[Session]:
    return _create_sessionmaker(tables or Base.metadata.sorted_tables, static_pool=static_pool)


__all__ = [
    "EDO_TABLES",
    "WEBHOOK_INTAKE_TABLES",
    "WEBHOOK_TABLES",
    "make_sqlite_session",
    "make_sqlite_session_factory",
]
