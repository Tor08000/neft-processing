from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as app_main
from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import Document, DocumentFile, DocumentStatus, DocumentType
from app.services.legal_graph import LegalGraphBuilder


def _clone_tables_without_duplicate_indexes(*tables):
    metadata = MetaData()
    cloned_tables = []
    for table in tables:
        cloned = table.to_metadata(metadata)
        seen = set()
        for index in list(cloned.indexes):
            if index.name in seen:
                cloned.indexes.remove(index)
            else:
                seen.add(index.name)
        cloned_tables.append(cloned)
    return cloned_tables


@pytest.fixture()
def db_session_factory(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    monkeypatch.setattr(app_main.settings, "APP_ENV", "dev", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    monkeypatch.setattr(LegalGraphBuilder, "ensure_document_ack_graph", lambda self, **kwargs: None)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    for table in _clone_tables_without_duplicate_indexes(
        Document.__table__,
        DocumentFile.__table__,
        DocumentAcknowledgement.__table__,
        AuditLog.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    testing_session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield testing_session_local
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _cleanup(db_session_factory: sessionmaker[Session]) -> None:
    with db_session_factory() as db:
        db.execute(text("DELETE FROM document_acknowledgements"))
        db.execute(text("DELETE FROM audit_log"))
        db.execute(text("DELETE FROM document_files"))
        db.execute(text("DELETE FROM documents"))
        db.commit()


def _seed_issued_document(db: Session, *, doc_hash: str) -> str:
    document_id = str(uuid4())
    file_id = str(uuid4())
    object_key = f"documents/{document_id}.pdf"

    db.execute(
        text(
            """
            INSERT INTO documents (
                id,
                tenant_id,
                client_id,
                document_type,
                doc_type,
                direction,
                title,
                sender_type,
                period_from,
                period_to,
                status,
                version,
                number
            ) VALUES (
                :id,
                :tenant_id,
                :client_id,
                :document_type,
                :doc_type,
                :direction,
                :title,
                :sender_type,
                :period_from,
                :period_to,
                :status,
                :version,
                :number
            )
            """
        ),
        {
            "id": document_id,
            "tenant_id": 1,
            "client_id": "client-a",
            "document_type": DocumentType.ACT.value,
            "doc_type": DocumentType.ACT.value,
            "direction": "INBOUND",
            "title": "Inbound act",
            "sender_type": "NEFT",
            "period_from": date(2026, 3, 1),
            "period_to": date(2026, 3, 31),
            "status": DocumentStatus.ISSUED.value,
            "version": 1,
            "number": "ACT-001",
        },
    )
    db.execute(
        text(
            """
            INSERT INTO document_files (
                id,
                document_id,
                storage_key,
                filename,
                mime,
                size,
                file_type,
                bucket,
                object_key,
                sha256,
                size_bytes,
                content_type
            ) VALUES (
                :id,
                :document_id,
                :storage_key,
                :filename,
                :mime,
                :size,
                :file_type,
                :bucket,
                :object_key,
                :sha256,
                :size_bytes,
                :content_type
            )
            """
        ),
        {
            "id": file_id,
            "document_id": document_id,
            "storage_key": object_key,
            "filename": "act.pdf",
            "mime": "application/pdf",
            "size": 123,
            "file_type": "PDF",
            "bucket": "documents",
            "object_key": object_key,
            "sha256": doc_hash,
            "size_bytes": 123,
            "content_type": "application/pdf",
        },
    )
    db.commit()
    return document_id


def _client_owner_payload() -> dict:
    return {
        "client_id": "client-a",
        "tenant_id": 1,
        "email": "client@example.com",
        "sub": "10000000-0000-0000-0000-000000000001",
        "user_id": "10000000-0000-0000-0000-000000000001",
        "roles": ["CLIENT_OWNER"],
        "role": "CLIENT_OWNER",
    }


def test_canonical_ack_success_reuses_legacy_invariants(db_session_factory):
    _cleanup(db_session_factory)
    doc_hash = "a" * 64
    with db_session_factory() as db:
        document_id = _seed_issued_document(db, doc_hash=doc_hash)

    app.dependency_overrides[client_portal_user] = _client_owner_payload
    with TestClient(app) as api_client:
        response = api_client.post(f"/api/core/client/documents/{document_id}/ack")

    assert response.status_code == 201
    payload = response.json()
    assert payload["acknowledged"] is True
    assert payload["document_type"] == DocumentType.ACT.value
    assert payload["document_hash"] == doc_hash
    assert payload["document_object_key"] == f"documents/{document_id}.pdf"
    assert payload["ack_at"] is not None

    with db_session_factory() as db:
        document_row = db.execute(
            text("SELECT status, ack_at FROM documents WHERE id = :id"),
            {"id": document_id},
        ).one()
        acknowledgement_row = db.execute(
            text(
                """
                SELECT document_hash, document_object_key, ack_by_email
                FROM document_acknowledgements
                WHERE document_id = :id
                """
            ),
            {"id": document_id},
        ).one()
        audit_row = db.execute(
            text(
                """
                SELECT after
                FROM audit_log
                WHERE event_type = 'DOCUMENT_ACKNOWLEDGED' AND entity_id = :id
                """
            ),
            {"id": document_id},
        ).one()

    audit_after = json.loads(audit_row.after) if isinstance(audit_row.after, str) else audit_row.after
    assert document_row.status == DocumentStatus.ACKNOWLEDGED.value
    assert document_row.ack_at is not None
    assert acknowledgement_row.document_hash == doc_hash
    assert acknowledgement_row.document_object_key == f"documents/{document_id}.pdf"
    assert acknowledgement_row.ack_by_email == "client@example.com"
    assert audit_after["document_hash"] == doc_hash
    assert audit_after["ack_hash"]


def test_canonical_ack_is_idempotent_for_existing_ack(db_session_factory):
    _cleanup(db_session_factory)
    doc_hash = "b" * 64
    with db_session_factory() as db:
        document_id = _seed_issued_document(db, doc_hash=doc_hash)

    app.dependency_overrides[client_portal_user] = _client_owner_payload
    with TestClient(app) as api_client:
        first = api_client.post(f"/api/core/client/documents/{document_id}/ack")
        second = api_client.post(f"/api/core/client/documents/{document_id}/ack")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["acknowledged"] is True
    assert second.json()["acknowledged"] is True
    assert second.json()["ack_at"] == first.json()["ack_at"]
    assert second.json()["document_hash"] == doc_hash

    with db_session_factory() as db:
        ack_count = db.execute(
            text("SELECT COUNT(*) FROM document_acknowledgements WHERE document_id = :id"),
            {"id": document_id},
        ).scalar_one()
        audit_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM audit_log
                WHERE event_type = 'DOCUMENT_ACKNOWLEDGED' AND entity_id = :id
                """
            ),
            {"id": document_id},
        ).scalar_one()

    assert ack_count == 1
    assert audit_count == 1
