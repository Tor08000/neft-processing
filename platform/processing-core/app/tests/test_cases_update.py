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


def test_update_case_status_adds_comment(make_jwt, client: TestClient, db_session: Session):
    case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.OPERATION,
        entity_id="op-1",
        title="case-1",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by="admin",
    )
    db_session.add(case)
    db_session.commit()

    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1, "email": "ops@neft.io"})
    resp = client.patch(
        f"/api/core/cases/{case.id}",
        headers=_auth_headers(token),
        json={"status": "IN_PROGRESS", "assigned_to": "ops@neft.io", "priority": "HIGH"},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "IN_PROGRESS"
    assert payload["priority"] == "HIGH"

    comments = db_session.query(CaseComment).filter(CaseComment.case_id == case.id).all()
    assert any("Status changed" in comment.body for comment in comments)
