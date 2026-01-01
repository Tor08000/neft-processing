from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models.cases import Case, CaseKind, CasePriority, CaseQueue, CaseStatus


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Case.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Case.__table__.drop(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _make_case(
    *,
    tenant_id: int,
    queue: CaseQueue,
    escalation_level: int,
    now: datetime,
    first_response_due_at: datetime | None = None,
    resolve_due_at: datetime | None = None,
) -> Case:
    return Case(
        tenant_id=tenant_id,
        kind=CaseKind.OPERATION,
        entity_id="op-1",
        kpi_key=None,
        window_days=None,
        title=f"Case {queue.value}",
        status=CaseStatus.TRIAGE,
        queue=queue,
        priority=CasePriority.MEDIUM,
        escalation_level=escalation_level,
        first_response_due_at=first_response_due_at,
        resolve_due_at=resolve_due_at,
        created_at=now,
        updated_at=now,
        last_activity_at=now - timedelta(minutes=5),
    )


def test_list_cases_filters_queue_sla_escalation(make_jwt, client: TestClient, db_session: Session):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 55, "email": "admin@neft.io"})
    now = datetime.now(timezone.utc)
    breached_case = _make_case(
        tenant_id=55,
        queue=CaseQueue.FRAUD_OPS,
        escalation_level=1,
        now=now,
        first_response_due_at=now - timedelta(minutes=10),
    )
    on_track_case = _make_case(
        tenant_id=55,
        queue=CaseQueue.FINANCE_OPS,
        escalation_level=0,
        now=now,
        first_response_due_at=now + timedelta(minutes=30),
    )
    db_session.add_all([breached_case, on_track_case])
    db_session.commit()

    resp_queue = client.get(
        "/api/core/cases?queue=FRAUD_OPS",
        headers=_auth_headers(token),
    )
    assert resp_queue.status_code == 200
    assert len(resp_queue.json()["items"]) == 1

    resp_sla = client.get(
        "/api/core/cases?sla_state=BREACHED",
        headers=_auth_headers(token),
    )
    assert resp_sla.status_code == 200
    assert len(resp_sla.json()["items"]) == 1

    resp_escalation = client.get(
        "/api/core/cases?escalation_level_min=1",
        headers=_auth_headers(token),
    )
    assert resp_escalation.status_code == 200
    assert len(resp_escalation.json()["items"]) == 1
