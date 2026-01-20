import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.ops import OpsEscalationPriority, OpsEscalationSource, OpsEscalationTarget
from app.models.unified_explain import PrimaryReason
from app.services.ops.escalations import create_escalation_if_missing


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


def test_snapshot_immutable_on_duplicate(db_session: Session):
    first = create_escalation_if_missing(
        db_session,
        tenant_id=1,
        target=OpsEscalationTarget.COMPLIANCE,
        priority=OpsEscalationPriority.CRITICAL,
        primary_reason=PrimaryReason.RISK,
        subject_type="FUEL_TX",
        subject_id="fuel-99",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        unified_explain_snapshot_hash="snap-original",
        unified_explain_snapshot={"primary_reason": "RISK", "snapshot": "v1"},
    )
    db_session.commit()

    duplicate = create_escalation_if_missing(
        db_session,
        tenant_id=1,
        target=OpsEscalationTarget.COMPLIANCE,
        priority=OpsEscalationPriority.CRITICAL,
        primary_reason=PrimaryReason.RISK,
        subject_type="FUEL_TX",
        subject_id="fuel-99",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        idempotency_key=first.escalation.idempotency_key,
        unified_explain_snapshot_hash="snap-updated",
        unified_explain_snapshot={"primary_reason": "RISK", "snapshot": "v2"},
    )
    db_session.commit()

    assert duplicate.created is False
    assert duplicate.escalation.unified_explain_snapshot_hash == "snap-original"
    assert duplicate.escalation.unified_explain_snapshot == {"primary_reason": "RISK", "snapshot": "v1"}
