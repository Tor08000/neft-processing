from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints.support_requests import router as support_requests_router
from app.models.audit_log import AuditLog
from app.models.cases import Case, CaseKind, CaseQueue
from app.models.support_request import SupportRequest, SupportRequestScopeType, SupportRequestStatus, SupportRequestSubjectType
from app.tests._scoped_router_harness import (
    SUPPORT_REQUEST_TEST_TABLES,
    router_client_context,
    scoped_session_context,
    support_requests_dependency_overrides,
)


@pytest.fixture
def session() -> Session:
    with scoped_session_context(tables=SUPPORT_REQUEST_TEST_TABLES) as db:
        yield db


@pytest.fixture
def client(session: Session) -> TestClient:
    with router_client_context(
        router=support_requests_router,
        db_session=session,
        dependency_overrides=support_requests_dependency_overrides(),
    ) as test_client:
        yield test_client


def test_support_request_create_creates_canonical_case_without_legacy_duplicate(
    make_jwt,
    client: TestClient,
    session: Session,
):
    token = make_jwt(roles=("CLIENT_OWNER",), client_id="client-1", extra={"tenant_id": 1})
    payload = {
        "scope_type": "CLIENT",
        "subject_type": "ORDER",
        "subject_id": str(uuid4()),
        "title": "Проблема с заказом",
        "description": "Документ не подписывается",
        "correlation_id": "corr-1",
    }

    response = client.post(
        "/api/v1/support/requests",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "OPEN"
    assert body["correlation_id"] == "corr-1"

    case = session.query(Case).filter(Case.id == body["id"]).one()
    assert case.kind == CaseKind.ORDER
    assert case.entity_type == "ORDER"
    assert case.entity_id == payload["subject_id"]
    assert case.queue == CaseQueue.SUPPORT
    assert case.client_id == "client-1"
    assert session.query(SupportRequest).count() == 0

    audit_entry = (
        session.query(AuditLog)
        .filter(AuditLog.entity_id == body["id"])
        .filter(AuditLog.event_type == "SUPPORT_REQUEST_CREATED")
        .one()
    )
    assert audit_entry.action == "CREATE"
    assert audit_entry.after["case_id"] == body["id"]


def test_support_request_status_change_materializes_legacy_row_to_case(
    session: Session,
    client: TestClient,
    make_jwt,
):
    support_request = SupportRequest(
        tenant_id=1,
        client_id="client-1",
        created_by_user_id="user-1",
        scope_type=SupportRequestScopeType.CLIENT,
        subject_type=SupportRequestSubjectType.DOCUMENT,
        subject_id=str(uuid4()),
        title="Тест",
        description="Описание",
        status=SupportRequestStatus.OPEN,
    )
    session.add(support_request)
    session.commit()

    admin_token = make_jwt(roles=("ADMIN", "ADMIN_FINANCE"), extra={"tenant_id": 1})

    response = client.post(
        f"/api/v1/support/requests/{support_request.id}/status",
        json={"status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"

    session.refresh(support_request)
    assert support_request.status == SupportRequestStatus.IN_PROGRESS

    case = session.query(Case).filter(Case.id == str(support_request.id)).one()
    assert case.kind == CaseKind.INCIDENT
    assert case.entity_type == "DOCUMENT"
    assert case.client_id == "client-1"
    assert case.queue == CaseQueue.SUPPORT

    audit_entry = (
        session.query(AuditLog)
        .filter(AuditLog.entity_id == str(support_request.id))
        .filter(AuditLog.event_type == "SUPPORT_REQUEST_STATUS_CHANGED")
        .one()
    )
    assert audit_entry.after["status"] == "IN_PROGRESS"


def test_support_request_list_materializes_legacy_rows_and_returns_compat_shape(
    session: Session,
    client: TestClient,
    make_jwt,
):
    support_request = SupportRequest(
        tenant_id=1,
        client_id="client-1",
        created_by_user_id="user-1",
        scope_type=SupportRequestScopeType.CLIENT,
        subject_type=SupportRequestSubjectType.OTHER,
        subject_id=None,
        title="Новая тема",
        description="Описание",
        status=SupportRequestStatus.WAITING,
    )
    session.add(support_request)
    session.commit()

    token = make_jwt(roles=("CLIENT_OWNER",), client_id="client-1", sub="user-1", extra={"tenant_id": 1})
    response = client.get(
        "/api/v1/support/requests?status=WAITING",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(support_request.id)
    assert body["items"][0]["status"] == "WAITING"
    assert body["items"][0]["scope_type"] == "CLIENT"

    case = session.query(Case).filter(Case.id == str(support_request.id)).one()
    assert case.kind == CaseKind.SUPPORT
    assert case.entity_type == "OTHER"


def test_support_request_create_accepts_uuid_like_client_tenant_claim(
    make_jwt,
    client: TestClient,
    session: Session,
):
    token = make_jwt(
        roles=("CLIENT_OWNER",),
        client_id="client-1",
        extra={"tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c"},
    )
    payload = {
        "scope_type": "CLIENT",
        "subject_type": "OTHER",
        "subject_id": None,
        "title": "Нужна помощь",
        "description": "Проверка UUID-like tenant claim",
        "correlation_id": "corr-uuid-tenant",
    }

    response = client.post(
        "/api/v1/support/requests",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert session.query(Case).count() == 1
