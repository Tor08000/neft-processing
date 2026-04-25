from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints.edo_events import router as edo_events_router
from app.db import get_db
from app.models.audit_log import AuditLog
from app.models.documents import (
    Document,
    DocumentDirection,
    DocumentEdoStatus,
    DocumentStatus,
    DocumentType,
)
from app.tests._scoped_router_harness import scoped_session_context


EDO_EVENTS_TEST_TABLES = (
    AuditLog.__table__,
    Document.__table__,
    DocumentEdoStatus.__table__,
)


@pytest.fixture
def session() -> Session:
    with scoped_session_context(tables=EDO_EVENTS_TEST_TABLES) as db:
        yield db


@pytest.fixture
def api_client(session: Session):
    app = FastAPI()
    app.include_router(edo_events_router)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client


def test_edo_event_updates_status_and_audit(session: Session, api_client: TestClient):
    document_id = str(uuid4())
    document = Document(
        id=document_id,
        tenant_id=1,
        client_id="client-1",
        direction=DocumentDirection.OUTBOUND,
        title="January invoice",
        document_type=DocumentType.INVOICE,
        period_from=date(2025, 1, 1),
        period_to=date(2025, 1, 31),
        status=DocumentStatus.ISSUED,
    )
    session.add(document)
    session.commit()

    payload = {
        "event_id": str(uuid4()),
        "occurred_at": "2025-01-01T00:00:00Z",
        "correlation_id": "corr-edo-1",
        "trace_id": "trace-edo-1",
        "schema_version": "1.0",
        "event_type": "EDO_DOCUMENT_SENT",
        "payload": {
            "document_id": document_id,
            "signature_id": None,
            "provider": "DIADOK",
            "status": "SENT",
            "provider_message_id": "msg-1",
        },
    }

    response = api_client.post("/api/v1/edo/events", json=payload)

    assert response.status_code == 202
    record = (
        session.query(DocumentEdoStatus)
        .filter(DocumentEdoStatus.document_id == document_id)
        .one()
    )
    assert record.status.value == "SENT"
    assert record.provider_message_id == "msg-1"

    audit_entry = (
        session.query(AuditLog)
        .filter(AuditLog.entity_id == str(record.id))
        .filter(AuditLog.event_type == "EDO_DOCUMENT_SENT")
        .one()
    )
    assert audit_entry.action == "STATUS_UPDATED"
