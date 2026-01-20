from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.ops import OpsEscalation, OpsEscalationPriority, OpsEscalationSource, OpsEscalationTarget
from app.models.unified_explain import PrimaryReason, UnifiedExplainSnapshot
from app.services.audit_service import AuditService
from app.services.ops.escalations import create_escalation_if_missing, scan_explain_sla_expiry


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


def test_create_escalation_idempotent(db_session: Session):
    result = create_escalation_if_missing(
        db_session,
        tenant_id=1,
        target=OpsEscalationTarget.FINANCE,
        priority=OpsEscalationPriority.HIGH,
        primary_reason=PrimaryReason.MONEY,
        subject_type="INVOICE",
        subject_id="inv-1",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        client_id="client-1",
        unified_explain_snapshot_hash="snap-1",
        unified_explain_snapshot={"primary_reason": "MONEY"},
    )
    db_session.commit()

    duplicate = create_escalation_if_missing(
        db_session,
        tenant_id=1,
        target=OpsEscalationTarget.FINANCE,
        priority=OpsEscalationPriority.HIGH,
        primary_reason=PrimaryReason.MONEY,
        subject_type="INVOICE",
        subject_id="inv-1",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        client_id="client-1",
        idempotency_key=result.escalation.idempotency_key,
        unified_explain_snapshot_hash="snap-1",
        unified_explain_snapshot={"primary_reason": "MONEY"},
    )
    db_session.commit()

    assert result.created is True
    assert duplicate.created is False
    assert db_session.query(OpsEscalation).count() == 1


def test_scan_sla_expiry_creates_escalation(db_session: Session):
    now = datetime.now(timezone.utc)
    snapshot = UnifiedExplainSnapshot(
        tenant_id=1,
        subject_type="FUEL_TX",
        subject_id="fuel-1",
        snapshot_hash="hash-1",
        snapshot_json={
            "primary_reason": "RISK",
            "subject": {"type": "FUEL_TX", "id": "fuel-1", "client_id": "client-1"},
            "ids": {"risk_decision_id": "risk-1", "invoice_id": "inv-1"},
            "sla": {
                "started_at": (now - timedelta(minutes=90)).isoformat(),
                "expires_at": (now - timedelta(minutes=5)).isoformat(),
                "remaining_minutes": 0,
            },
        },
    )
    db_session.add(snapshot)
    db_session.commit()

    created = scan_explain_sla_expiry(db_session, audit=AuditService(db_session))
    db_session.commit()
    assert len(created) == 1

    escalation = created[0]
    assert escalation.priority == OpsEscalationPriority.CRITICAL
    assert escalation.primary_reason == PrimaryReason.RISK
    assert escalation.target == OpsEscalationTarget.COMPLIANCE

    created_again = scan_explain_sla_expiry(db_session, audit=AuditService(db_session))
    db_session.commit()
    assert len(created_again) == 0
    assert db_session.query(OpsEscalation).count() == 1
