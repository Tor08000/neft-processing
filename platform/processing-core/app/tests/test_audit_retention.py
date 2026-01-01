from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import engine
from app.db.schema import DB_SCHEMA
from app.models.audit_retention import AuditLegalHold, AuditLegalHoldScope, AuditPurgeLog
from app.models.cases import Case, CaseKind, CasePriority, CaseQueue, CaseSnapshot, CaseStatus
from app.services.audit_purge_service import purge_expired_exports
from app.tests.utils import ensure_connectable, get_database_url


def _make_alembic_config(db_url: str) -> Config:
    app_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(app_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(app_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Case.__table__.create(bind=engine)
    CaseSnapshot.__table__.create(bind=engine)
    AuditLegalHold.__table__.create(bind=engine)
    AuditPurgeLog.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        AuditPurgeLog.__table__.drop(bind=engine)
        AuditLegalHold.__table__.drop(bind=engine)
        CaseSnapshot.__table__.drop(bind=engine)
        Case.__table__.drop(bind=engine)
        engine.dispose()


def _create_case(db_session: Session) -> Case:
    case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.OPERATION,
        title="case",
        status=CaseStatus.TRIAGE,
        queue=CaseQueue.GENERAL,
        priority=CasePriority.MEDIUM,
        escalation_level=0,
    )
    db_session.add(case)
    db_session.commit()
    return case


def test_purge_snapshots_writes_purge_log(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    case = _create_case(db_session)
    snapshot = CaseSnapshot(
        id=str(uuid4()),
        case_id=case.id,
        explain_snapshot={"decision": "DECLINE"},
        created_at=now - timedelta(days=200),
    )
    db_session.add(snapshot)
    db_session.commit()

    result = purge_expired_exports(
        db_session,
        now=now,
        retention_days=30,
        dry_run=False,
        purged_by="test-suite",
    )
    db_session.commit()

    assert result.purged == 1
    assert db_session.query(CaseSnapshot).count() == 0
    log_entry = db_session.query(AuditPurgeLog).one()
    assert log_entry.entity_type == "case_snapshot"
    assert log_entry.case_id == case.id


def test_purge_respects_legal_hold(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    case = _create_case(db_session)
    snapshot = CaseSnapshot(
        id=str(uuid4()),
        case_id=case.id,
        explain_snapshot={"decision": "DECLINE"},
        created_at=now - timedelta(days=200),
    )
    hold = AuditLegalHold(
        scope=AuditLegalHoldScope.CASE.value,
        case_id=case.id,
        reason="legal hold",
        active=True,
    )
    db_session.add_all([snapshot, hold])
    db_session.commit()

    result = purge_expired_exports(
        db_session,
        now=now,
        retention_days=30,
        dry_run=False,
        purged_by="test-suite",
    )
    db_session.commit()

    assert result.purged == 0
    assert result.skipped_hold == 1
    assert db_session.query(CaseSnapshot).count() == 1
    assert db_session.query(AuditPurgeLog).count() == 0


def test_purge_dry_run_returns_candidates(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    case = _create_case(db_session)
    snapshot = CaseSnapshot(
        id=str(uuid4()),
        case_id=case.id,
        explain_snapshot={"decision": "DECLINE"},
        created_at=now - timedelta(days=200),
    )
    db_session.add(snapshot)
    db_session.commit()

    result = purge_expired_exports(
        db_session,
        now=now,
        retention_days=30,
        dry_run=True,
        purged_by="test-suite",
    )

    assert result.candidates == 1
    assert result.purged == 0
    assert db_session.query(CaseSnapshot).count() == 1
    assert db_session.query(AuditPurgeLog).count() == 0


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="WORM guard requires Postgres")
def test_case_events_worm_guard_blocks_update_and_delete() -> None:
    db_url = get_database_url()
    engine = ensure_connectable(db_url)
    alembic_cfg = _make_alembic_config(db_url)
    command.upgrade(alembic_cfg, "head")

    schema = DB_SCHEMA
    case_id = str(uuid4())
    event_id = str(uuid4())
    schema_prefix = f'"{schema}".' if schema else ""

    with engine.begin() as connection:
        connection.exec_driver_sql(f'SET search_path TO "{schema}"')
        connection.exec_driver_sql(
            f"""
            INSERT INTO {schema_prefix}cases (id, tenant_id, kind, title)
            VALUES (%s, %s, %s, %s)
            """,
            (case_id, 1, "operation", "case"),
        )
        connection.exec_driver_sql(
            f"""
            INSERT INTO {schema_prefix}case_events
                (id, case_id, seq, type, payload_redacted, prev_hash, hash)
            VALUES (%s, %s, %s, %s, %s::json, %s, %s)
            """,
            (
                event_id,
                case_id,
                1,
                "CASE_CREATED",
                json.dumps({"note": "hello"}),
                "GENESIS",
                "hash",
            ),
        )

        with pytest.raises(sa.exc.DBAPIError) as exc_info:
            connection.exec_driver_sql(
                f"UPDATE {schema_prefix}case_events SET payload_redacted = %s::json WHERE id = %s",
                (json.dumps({"tampered": True}), event_id),
            )
        assert "case_events is WORM" in str(exc_info.value)

        with pytest.raises(sa.exc.DBAPIError) as exc_info:
            connection.exec_driver_sql(
                f"DELETE FROM {schema_prefix}case_events WHERE id = %s",
                (event_id,),
            )
        assert "case_events is WORM" in str(exc_info.value)
