from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import app
from app.models.audit_log import AuditLog
from app.models.documents import Document, DocumentEdoStatus, DocumentStatus, DocumentType


@pytest.fixture
def session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_edo_event_updates_status_and_audit(session: Session):
    document_id = str(uuid4())
    document = Document(
        id=document_id,
        tenant_id=1,
        client_id="client-1",
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

    with TestClient(app) as client:
        response = client.post("/api/v1/edo/events", json=payload)

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
