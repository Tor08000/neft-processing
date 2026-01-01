import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models.cases import Case, CaseComment, CaseSnapshot


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


def test_create_case_applies_queue_and_sla(make_jwt, client: TestClient):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1, "email": "admin@neft.io"})
    payload = {
        "kind": "operation",
        "entity_id": "op-999",
        "priority": "MEDIUM",
        "note": "Проверить причины отклонений",
        "explain": {"decision": "DECLINE", "reason_codes": ["velocity_high"]},
    }

    resp = client.post("/api/core/cases", headers=_auth_headers(token), json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["queue"] == "FRAUD_OPS"
    assert body["first_response_due_at"] is not None
    assert body["resolve_due_at"] is not None
