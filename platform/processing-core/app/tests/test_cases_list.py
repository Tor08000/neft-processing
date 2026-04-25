from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cases import Case, CaseKind, CasePriority, CaseQueue, CaseStatus
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


def test_list_cases_support_filters(make_jwt, client: TestClient, db_session: Session):
    support_case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.SUPPORT,
        entity_type="DOCUMENT",
        entity_id="doc-1",
        title="document-incident",
        description="подпись не проходит",
        status=CaseStatus.WAITING,
        queue=CaseQueue.SUPPORT,
        priority=CasePriority.HIGH,
        created_by="user-1",
        client_id="client-1",
    )
    dispute_case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.DISPUTE,
        entity_type="INVOICE",
        entity_id="inv-1",
        title="invoice dispute",
        description="нужна сверка",
        status=CaseStatus.IN_PROGRESS,
        queue=CaseQueue.FINANCE_OPS,
        priority=CasePriority.MEDIUM,
        created_by="user-2",
        client_id="client-1",
    )
    db_session.add_all([support_case, dispute_case])
    db_session.commit()

    token = make_jwt(roles=("ADMIN",), extra={"tenant_id": 1})
    response = client.get(
        "/api/core/cases?queue=SUPPORT&entity_type=DOCUMENT&q=подпись",
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == support_case.id
