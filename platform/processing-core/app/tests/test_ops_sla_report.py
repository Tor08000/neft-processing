from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db import Base
from app.db.types import new_uuid_str
from app.models.ops import OpsEscalation, OpsEscalationPriority, OpsEscalationSource, OpsEscalationStatus, OpsEscalationTarget
from app.models.unified_explain import PrimaryReason
from app.services.ops.sla_reports import build_sla_report


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _add_escalation(db_session: Session, **kwargs) -> OpsEscalation:
    escalation = OpsEscalation(**kwargs)
    db_session.add(escalation)
    return escalation


def test_sla_report_counts(db_session: Session):
    report_date = date(2025, 1, 15)
    created_at = datetime(2025, 1, 15, 9, 0, tzinfo=timezone.utc)

    _add_escalation(
        db_session,
        id=new_uuid_str(),
        tenant_id=1,
        target=OpsEscalationTarget.COMPLIANCE,
        status=OpsEscalationStatus.CLOSED,
        priority=OpsEscalationPriority.CRITICAL,
        primary_reason=PrimaryReason.RISK,
        subject_type="FUEL_TX",
        subject_id="fuel-1",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        sla_started_at=created_at,
        sla_expires_at=created_at + timedelta(minutes=120),
        created_at=created_at,
        closed_at=created_at + timedelta(minutes=60),
        unified_explain_snapshot_hash="snap-1",
        unified_explain_snapshot={"primary_reason": "RISK"},
        idempotency_key="idem-1",
    )

    _add_escalation(
        db_session,
        id=new_uuid_str(),
        tenant_id=1,
        target=OpsEscalationTarget.CRM,
        status=OpsEscalationStatus.OPEN,
        priority=OpsEscalationPriority.MEDIUM,
        primary_reason=PrimaryReason.LIMIT,
        subject_type="ORDER",
        subject_id="order-1",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        sla_started_at=created_at,
        sla_expires_at=created_at + timedelta(minutes=30),
        created_at=created_at,
        unified_explain_snapshot_hash="snap-2",
        unified_explain_snapshot={"primary_reason": "LIMIT"},
        idempotency_key="idem-2",
    )

    _add_escalation(
        db_session,
        id=new_uuid_str(),
        tenant_id=1,
        target=OpsEscalationTarget.FINANCE,
        status=OpsEscalationStatus.CLOSED,
        priority=OpsEscalationPriority.HIGH,
        primary_reason=PrimaryReason.MONEY,
        subject_type="INVOICE",
        subject_id="inv-1",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        sla_started_at=created_at,
        sla_expires_at=created_at + timedelta(minutes=90),
        created_at=created_at,
        closed_at=created_at + timedelta(minutes=140),
        unified_explain_snapshot_hash="snap-3",
        unified_explain_snapshot={"primary_reason": "MONEY"},
        idempotency_key="idem-3",
    )

    db_session.commit()

    now = created_at + timedelta(hours=4)
    report = build_sla_report(db_session, tenant_id=1, period=report_date, now=now)

    assert report["period"] == "2025-01-15"
    assert report["total"] == 3
    assert report["closed_within_sla"] == 1
    assert report["overdue"] == 2
    assert report["by_primary_reason"][PrimaryReason.RISK]["total"] == 1
    assert report["by_primary_reason"][PrimaryReason.RISK]["overdue"] == 0
    assert report["by_primary_reason"][PrimaryReason.LIMIT]["overdue"] == 1
    assert report["by_primary_reason"][PrimaryReason.MONEY]["overdue"] == 1
