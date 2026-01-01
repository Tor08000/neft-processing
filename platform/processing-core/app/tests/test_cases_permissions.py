from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models.cases import Case, CaseComment, CaseKind, CasePriority, CaseSnapshot, CaseStatus


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Case.__table__.create(bind=engine)
    CaseSnapshot.__table__.create(bind=engine)
    CaseComment.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        CaseComment.__table__.drop(bind=engine)
        CaseSnapshot.__table__.drop(bind=engine)
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


def test_client_cannot_update_case(make_jwt, client: TestClient, db_session: Session):
    case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.OPERATION,
        entity_id="op-1",
        title="client-case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by="user-1",
    )
    db_session.add(case)
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", extra={"tenant_id": 1})
    resp = client.patch(
        f"/api/core/cases/{case.id}",
        headers=_auth_headers(token),
        json={"status": "IN_PROGRESS"},
    )
    assert resp.status_code == 403


def test_client_list_scoped_to_creator(make_jwt, client: TestClient, db_session: Session):
    case_a = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.OPERATION,
        entity_id="op-1",
        title="case-a",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by="user-1",
    )
    case_b = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.OPERATION,
        entity_id="op-2",
        title="case-b",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by="user-2",
    )
    db_session.add_all([case_a, case_b])
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", sub="user-1", extra={"tenant_id": 1})
    resp = client.get("/api/core/cases", headers=_auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == case_a.id
