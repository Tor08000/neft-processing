import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cases import Case, CaseComment, CaseEvent, CaseSnapshot
from app.routers.cases import router as cases_router
from app.tests._scoped_router_harness import CASES_TEST_TABLES, cases_dependency_overrides, router_client_context, scoped_session_context


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def db_session() -> Session:
    with scoped_session_context(tables=CASES_TEST_TABLES) as session:
        yield session


@pytest.fixture()
def client(db_session: Session):
    with router_client_context(
        router=cases_router,
        prefix="/api/core",
        db_session=db_session,
        dependency_overrides=cases_dependency_overrides(),
    ) as test_client:
        yield test_client


def test_create_case_stores_snapshot(make_jwt, client: TestClient, db_session: Session):
    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1, "email": "admin@neft.io"})
    payload = {
        "kind": "operation",
        "entity_id": "op-123",
        "priority": "MEDIUM",
        "note": "Проверить причины отказов по SLA",
        "explain": {"decision": "DECLINE", "score": 82},
        "diff": {"score_diff": {"risk_before": 0.82, "risk_after": 0.47}},
        "selected_actions": [{"code": "REQUEST_DOCS", "what_if": {"impact": 0.1}}],
    }

    resp = client.post("/api/core/cases", headers=_auth_headers(token), json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "TRIAGE"
    case_id = body["id"]

    snapshot = db_session.query(CaseSnapshot).filter(CaseSnapshot.case_id == case_id).one()
    assert snapshot.explain_snapshot["decision"] == "DECLINE"
    assert snapshot.note == payload["note"]
    assert db_session.query(CaseComment).filter(CaseComment.case_id == case_id).count() == 3
