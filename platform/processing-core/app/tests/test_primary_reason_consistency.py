import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db import Base
from app.models.ops import OpsEscalationPriority, OpsEscalationSource, OpsEscalationTarget
from app.models.unified_explain import PrimaryReason
from app.services.ops.escalations import create_escalation_if_missing
from app.services.ops.reason_codes import OpsReasonCode, get_primary_reason, get_target_for_reason


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


def test_reason_code_mapping_matches_primary_and_target():
    for code in OpsReasonCode:
        assert isinstance(get_primary_reason(code), PrimaryReason)
        assert isinstance(get_target_for_reason(code), OpsEscalationTarget)


def test_escalation_reason_code_inferred_from_snapshot(db_session: Session):
    result = create_escalation_if_missing(
        db_session,
        tenant_id=1,
        target=OpsEscalationTarget.CRM,
        priority=OpsEscalationPriority.MEDIUM,
        primary_reason=PrimaryReason.LIMIT,
        subject_type="FUEL_TX",
        subject_id="fuel-1",
        source=OpsEscalationSource.MANUAL_FROM_EXPLAIN,
        unified_explain_snapshot_hash="snap-limit",
        unified_explain_snapshot={"result": {"decline_code": "LIMIT_EXCEEDED_AMOUNT"}},
    )
    db_session.commit()

    assert result.escalation.reason_code == OpsReasonCode.LIMIT_EXCEEDED.value
