import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.ops import OpsEscalationPriority, OpsEscalationSource, OpsEscalationTarget
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
        target=OpsEscalationTarget.LOGISTICS,
        priority=OpsEscalationPriority.MEDIUM,
        primary_reason=PrimaryReason.LOGISTICS,
        subject_type="ORDER",
        subject_id="order-42",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        unified_explain_snapshot_hash="snap-reason",
        unified_explain_snapshot={"primary_reason": "LOGISTICS"},
    )
    db_session.commit()
    return result.escalation


def test_ack_reason_code_required(db_session: Session):
    escalation = _create_escalation(db_session)

    with pytest.raises(ValueError):
        ack_escalation(db_session, escalation=escalation, reason_code=" ", reason_text=None, actor="admin-1")


def test_close_reason_code_required(db_session: Session):
    escalation = _create_escalation(db_session)

    with pytest.raises(ValueError):
        close_escalation(
            db_session, escalation=escalation, reason_code="", reason_text=None, actor="admin-1", allow_from_open=True
        )


def test_close_other_requires_text(db_session: Session):
    escalation = _create_escalation(db_session)

    with pytest.raises(ValueError):
        close_escalation(
            db_session,
            escalation=escalation,
            reason_code="CLOSE_OTHER",
            reason_text="",
            actor="admin-1",
            allow_from_open=True,
        )
