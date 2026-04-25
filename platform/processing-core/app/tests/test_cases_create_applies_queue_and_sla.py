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
