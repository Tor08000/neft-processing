from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.audit_log import AuditLog
from app.models.ops import OpsEscalation
from app.models.unified_explain import UnifiedExplainSnapshot

OPS_TEST_TABLES = [
    AuditLog.__table__,
    OpsEscalation.__table__,
    UnifiedExplainSnapshot.__table__,
]


def build_ops_session_factory() -> tuple[sessionmaker[Session], object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=OPS_TEST_TABLES)
    return (
        sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine, class_=Session),
        engine,
    )


def teardown_ops_session_factory(engine: object) -> None:
    Base.metadata.drop_all(bind=engine, tables=OPS_TEST_TABLES)
    engine.dispose()


__all__ = ["build_ops_session_factory", "teardown_ops_session_factory"]
