import pytest
from sqlalchemy.orm import Session
from app.models.ops import OpsEscalationPriority, OpsEscalationSource, OpsEscalationTarget
from app.models.unified_explain import PrimaryReason
from app.services.ops.escalations import create_escalation_if_missing
from app.tests._ops_test_harness import build_ops_session_factory, teardown_ops_session_factory


@pytest.fixture()
def db_session() -> Session:
    SessionLocal, engine = build_ops_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        teardown_ops_session_factory(engine)


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
