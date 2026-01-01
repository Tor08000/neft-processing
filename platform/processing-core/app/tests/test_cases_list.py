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


def _seed_case(db_session: Session, *, tenant_id: int, title: str, created_by: str) -> Case:
    case = Case(
        id=str(uuid4()),
        tenant_id=tenant_id,
        kind=CaseKind.OPERATION,
        entity_id="op-1",
        title=title,
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by=created_by,
    )
    db_session.add(case)
    db_session.commit()
    return case


def test_list_cases_pagination(make_jwt, client: TestClient, db_session: Session):
    _seed_case(db_session, tenant_id=1, title="case-1", created_by="user-1")
    _seed_case(db_session, tenant_id=1, title="case-2", created_by="user-1")
    _seed_case(db_session, tenant_id=2, title="case-3", created_by="user-2")

    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})
    resp = client.get("/api/core/cases?limit=1", headers=_auth_headers(token))

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["next_cursor"] is not None

    resp_next = client.get(f"/api/core/cases?limit=1&cursor={data['next_cursor']}", headers=_auth_headers(token))
    assert resp_next.status_code == 200
    data_next = resp_next.json()
    assert len(data_next["items"]) == 1
