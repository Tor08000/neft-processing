from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cases import Case, CaseKind, CasePriority, CaseStatus
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


def test_client_cannot_update_case(make_jwt, client: TestClient, db_session: Session):
    case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.SUPPORT,
        client_id="client-1",
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


def test_client_list_scoped_to_client_and_unscoped_creator(make_jwt, client: TestClient, db_session: Session):
    case_a = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.SUPPORT,
        entity_id="op-1",
        title="case-a",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by="user-2",
        client_id="client-1",
    )
    case_b = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.SUPPORT,
        entity_id="op-2",
        title="case-b",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by="user-3",
        client_id="client-2",
    )
    case_c = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.SUPPORT,
        entity_id="op-3",
        title="case-c",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by="user-2",
    )
    db_session.add_all([case_a, case_b, case_c])
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", sub="user-2", extra={"tenant_id": 1})
    resp = client.get("/api/core/cases", headers=_auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert {item["id"] for item in data["items"]} == {case_a.id, case_c.id}


def test_partner_can_only_read_own_cases(make_jwt, client: TestClient, db_session: Session):
    case_a = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.ORDER,
        entity_type="ORDER",
        entity_id="order-1",
        title="partner-order-case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        partner_id="partner-1",
    )
    case_b = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.ORDER,
        entity_type="ORDER",
        entity_id="order-2",
        title="other-partner-order-case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        partner_id="partner-2",
    )
    db_session.add_all([case_a, case_b])
    db_session.commit()

    token = make_jwt(roles=("PARTNER_USER",), extra={"tenant_id": 1, "partner_id": "partner-1"})
    resp = client.get("/api/core/cases", headers=_auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == case_a.id

    missing = client.get(f"/api/core/cases/{case_b.id}", headers=_auth_headers(token))
    assert missing.status_code == 404


def test_client_can_open_legacy_marketplace_order_case_from_compat_tenant_zero(
    make_jwt,
    client: TestClient,
    db_session: Session,
):
    case = Case(
        id=str(uuid4()),
        tenant_id=0,
        kind=CaseKind.ORDER,
        entity_type="ORDER",
        entity_id="order-legacy",
        title="legacy-marketplace-order-case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        client_id="client-1",
        case_source_ref_type="MARKETPLACE_ORDER",
        case_source_ref_id=str(uuid4()),
    )
    db_session.add(case)
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", sub="user-1")
    response = client.get(f"/api/core/cases/{case.id}", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["case"]["id"] == case.id


def test_client_cannot_open_non_marketplace_legacy_tenant_zero_case(
    make_jwt,
    client: TestClient,
    db_session: Session,
):
    case = Case(
        id=str(uuid4()),
        tenant_id=0,
        kind=CaseKind.SUPPORT,
        entity_type="SUPPORT",
        entity_id="support-legacy",
        title="legacy-support-case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        client_id="client-1",
        case_source_ref_type="SUPPORT_TICKET",
        case_source_ref_id=str(uuid4()),
    )
    db_session.add(case)
    db_session.commit()

    token = make_jwt(roles=("CLIENT_USER",), client_id="client-1", sub="user-1")
    response = client.get(f"/api/core/cases/{case.id}", headers=_auth_headers(token))

    assert response.status_code == 404


def test_partner_can_open_legacy_marketplace_order_case_from_compat_tenant_zero(
    make_jwt,
    client: TestClient,
    db_session: Session,
):
    case = Case(
        id=str(uuid4()),
        tenant_id=0,
        kind=CaseKind.ORDER,
        entity_type="ORDER",
        entity_id="order-partner-legacy",
        title="legacy-partner-marketplace-order-case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        partner_id="partner-1",
        case_source_ref_type="MARKETPLACE_ORDER",
        case_source_ref_id=str(uuid4()),
    )
    db_session.add(case)
    db_session.commit()

    token = make_jwt(roles=("PARTNER_USER",), extra={"partner_id": "partner-1"})
    response = client.get(f"/api/core/cases/{case.id}", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["case"]["id"] == case.id


def test_client_list_accepts_uuid_like_tenant_claim(make_jwt, client: TestClient, db_session: Session):
    case = Case(
        id=str(uuid4()),
        tenant_id=1,
        kind=CaseKind.SUPPORT,
        entity_id="op-uuid",
        title="uuid-tenant-case",
        status=CaseStatus.TRIAGE,
        priority=CasePriority.MEDIUM,
        created_by="user-uuid",
        client_id="client-1",
    )
    db_session.add(case)
    db_session.commit()

    token = make_jwt(
        roles=("CLIENT_USER",),
        client_id="client-1",
        sub="user-uuid",
        extra={"tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c"},
    )
    resp = client.get("/api/core/cases", headers=_auth_headers(token))

    assert resp.status_code == 200
    assert resp.json()["total"] == 1
