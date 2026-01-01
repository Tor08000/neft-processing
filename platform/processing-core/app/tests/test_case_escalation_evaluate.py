from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.cases import (
    Case,
    CaseComment,
    CaseCommentType,
    CaseKind,
    CasePriority,
    CaseQueue,
    CaseStatus,
)
from app.services.case_escalation_service import evaluate_escalations


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Case.__table__.create(bind=engine)
    CaseComment.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        CaseComment.__table__.drop(bind=engine)
        Case.__table__.drop(bind=engine)
        engine.dispose()


def _make_case(now: datetime) -> Case:
    return Case(
        tenant_id=1,
        kind=CaseKind.OPERATION,
        entity_id="op-123",
        kpi_key=None,
        window_days=None,
        title="Case: operation op-123",
        status=CaseStatus.TRIAGE,
        queue=CaseQueue.GENERAL,
        priority=CasePriority.MEDIUM,
        escalation_level=0,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
    )


def test_first_response_breach_creates_escalation(db_session: Session):
    now = datetime.now(timezone.utc)
    case = _make_case(now)
    case.first_response_due_at = now - timedelta(minutes=5)
    case.last_activity_at = now - timedelta(minutes=10)
    db_session.add(case)
    db_session.commit()

    result = evaluate_escalations(db_session, now=now)
    db_session.commit()

    refreshed = db_session.query(Case).filter(Case.id == case.id).one()
    assert result["first_response"] == 1
    assert refreshed.escalation_level == 1
    comments = db_session.query(CaseComment).filter(CaseComment.case_id == case.id).all()
    assert any(comment.type == CaseCommentType.SYSTEM for comment in comments)


def test_resolve_breach_creates_escalation_level_two(db_session: Session):
    now = datetime.now(timezone.utc)
    case = _make_case(now)
    case.resolve_due_at = now - timedelta(minutes=5)
    case.escalation_level = 1
    db_session.add(case)
    db_session.commit()

    result = evaluate_escalations(db_session, now=now)
    db_session.commit()

    refreshed = db_session.query(Case).filter(Case.id == case.id).one()
    assert result["resolve"] == 1
    assert refreshed.escalation_level == 2


def test_resolved_case_is_not_escalated(db_session: Session):
    now = datetime.now(timezone.utc)
    case = _make_case(now)
    case.status = CaseStatus.RESOLVED
    case.first_response_due_at = now - timedelta(minutes=10)
    case.resolve_due_at = now - timedelta(minutes=5)
    db_session.add(case)
    db_session.commit()

    result = evaluate_escalations(db_session, now=now)
    db_session.commit()

    refreshed = db_session.query(Case).filter(Case.id == case.id).one()
    assert result == {"first_response": 0, "resolve": 0}
    assert refreshed.escalation_level == 0
