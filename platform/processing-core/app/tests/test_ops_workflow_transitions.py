import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.ops import OpsEscalationPriority, OpsEscalationSource, OpsEscalationStatus, OpsEscalationTarget
from app.models.unified_explain import PrimaryReason
from app.services.ops.escalations import ack_escalation, close_escalation, create_escalation_if_missing


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


def _create_escalation(db_session: Session):
    result = create_escalation_if_missing(
        db_session,
        tenant_id=1,
        target=OpsEscalationTarget.CRM,
        priority=OpsEscalationPriority.MEDIUM,
        primary_reason=PrimaryReason.LIMIT,
        subject_type="ORDER",
        subject_id="order-1",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        unified_explain_snapshot_hash="snap-ops",
        unified_explain_snapshot={"primary_reason": "LIMIT"},
    )
    db_session.commit()
    return result.escalation


def test_ops_workflow_transitions(db_session: Session):
    escalation = _create_escalation(db_session)

    acked = ack_escalation(
        db_session,
        escalation=escalation,
        reason_code="ACK_IN_REVIEW",
        reason_text="Reviewed",
        actor="admin-1",
    )
    db_session.commit()
    assert acked.status == OpsEscalationStatus.ACK
    assert acked.ack_reason_code == "ACK_IN_REVIEW"
    assert acked.ack_reason_text == "Reviewed"

    closed = close_escalation(
        db_session,
        escalation=escalation,
        reason_code="CLOSE_LIMIT_INCREASED",
        reason_text="Resolved",
        actor="admin-1",
    )
    db_session.commit()
    assert closed.status == OpsEscalationStatus.CLOSED
    assert closed.close_reason_code == "CLOSE_LIMIT_INCREASED"
    assert closed.close_reason_text == "Resolved"
    assert closed.closed_at is not None


def test_close_requires_admin_for_open_state(db_session: Session):
    escalation = _create_escalation(db_session)

    with pytest.raises(PermissionError):
        close_escalation(
            db_session,
            escalation=escalation,
            reason_code="CLOSE_DUPLICATE",
            reason_text="Force close",
            actor="user-1",
        )

    closed = close_escalation(
        db_session,
        escalation=escalation,
        reason_code="CLOSE_DUPLICATE",
        reason_text="Admin close",
        actor="admin-1",
        allow_from_open=True,
    )
    db_session.commit()
    assert closed.status == OpsEscalationStatus.CLOSED
    assert closed.closed_at is not None
