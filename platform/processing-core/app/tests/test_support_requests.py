from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.models.support_request import SupportRequest, SupportRequestScopeType, SupportRequestStatus, SupportRequestSubjectType


@pytest.fixture
def session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_support_request_create(make_jwt):
    token = make_jwt(roles=("CLIENT_OWNER",), client_id="client-1", extra={"tenant_id": 1})
    payload = {
        "scope_type": "CLIENT",
        "subject_type": "ORDER",
        "subject_id": str(uuid4()),
        "title": "Проблема с заказом",
        "description": "Документ не подписывается",
        "correlation_id": "corr-1",
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/support/requests",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "OPEN"
    assert body["correlation_id"] == "corr-1"


def test_support_request_status_change_emits_audit(session: Session, admin_token: str):
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

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/support/requests/{support_request.id}/status",
            json={"status": "IN_PROGRESS"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200

    audit_entry = (
        session.query(AuditLog)
        .filter(AuditLog.entity_id == str(support_request.id))
        .filter(AuditLog.event_type == "SUPPORT_REQUEST_STATUS_CHANGED")
        .one()
    )
    assert audit_entry.after["status"] == "IN_PROGRESS"


def test_support_request_create_audit_logged(session: Session, make_jwt):
    token = make_jwt(roles=("CLIENT_OWNER",), client_id="client-1", extra={"tenant_id": 1})
    payload = {
        "scope_type": "CLIENT",
        "subject_type": "OTHER",
        "title": "Новая тема",
        "description": "Описание",
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/support/requests",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    support_id = response.json()["id"]

    audit_entry = (
        session.query(AuditLog)
        .filter(AuditLog.entity_id == support_id)
        .filter(AuditLog.event_type == "SUPPORT_REQUEST_CREATED")
        .one()
    )
    assert audit_entry.action == "CREATE"
