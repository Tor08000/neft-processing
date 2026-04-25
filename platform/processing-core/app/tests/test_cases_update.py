from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cases import Case, CaseComment, CaseEvent, CaseKind, CasePriority, CaseSnapshot, CaseStatus
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
    assert any("Статус изменён" in comment.body for comment in comments)
    assert any("Назначено на ops@neft.io" in comment.body for comment in comments)
