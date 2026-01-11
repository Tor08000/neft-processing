from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_sessionmaker
from app.db.schema import DB_SCHEMA
from app.main import app
from app.models.legal_gate import LegalAcceptance, LegalDocument, LegalDocumentStatus, LegalSubjectType


def _truncate_legal_tables(db) -> None:
    db.execute(text(f"TRUNCATE {DB_SCHEMA}.legal_acceptances CASCADE"))
    db.execute(text(f"TRUNCATE {DB_SCHEMA}.legal_documents CASCADE"))
    db.commit()


def _seed_document(db, *, code: str, version: int, effective_from: datetime) -> LegalDocument:
    doc = LegalDocument(
        code=code,
        title=f"{code} v{version}",
        version=version,
        status=LegalDocumentStatus.PUBLISHED,
        effective_from=effective_from,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@pytest.fixture()
def db_session():
    session = get_sessionmaker()()
    _truncate_legal_tables(session)
    try:
        yield session
    finally:
        _truncate_legal_tables(session)
        session.close()


@pytest.fixture()
def client(admin_auth_headers):
    with TestClient(app) as api_client:
        api_client.headers.update(admin_auth_headers)
        yield api_client


def test_protected_requires_acceptance(client: TestClient, db_session):
    _seed_document(
        db_session,
        code="LEGAL_TERMS",
        version=1,
        effective_from=datetime.now(timezone.utc) - timedelta(days=1),
    )

    response = client.get(
        "/api/core/legal/protected",
        params={"subject_type": "CLIENT", "subject_id": "client-1"},
    )

    assert response.status_code == 428
    payload = response.json()["detail"]
    assert payload["error"] == "LEGAL_REQUIRED"
    assert payload["required"]


def test_acceptance_allows_access(client: TestClient, db_session):
    _seed_document(
        db_session,
        code="LEGAL_TERMS",
        version=1,
        effective_from=datetime.now(timezone.utc) - timedelta(days=1),
    )

    accept_response = client.post(
        "/api/core/legal/accept",
        json={"subject_type": "CLIENT", "subject_id": "client-1", "accept_all": True},
    )
    assert accept_response.status_code == 200

    response = client.get(
        "/api/core/legal/protected",
        params={"subject_type": "CLIENT", "subject_id": "client-1"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_required_returns_latest_version(client: TestClient, db_session):
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    today = datetime.now(timezone.utc)
    _seed_document(db_session, code="DATA_PROCESSING", version=1, effective_from=yesterday)
    _seed_document(db_session, code="DATA_PROCESSING", version=2, effective_from=today)

    response = client.get(
        "/api/core/legal/required",
        params={"subject_type": "CLIENT", "subject_id": "client-1"},
    )

    assert response.status_code == 200
    required = response.json()["required"]
    assert len(required) == 1
    assert required[0]["version"] == 2


def test_acceptance_is_immutable(db_session):
    doc = _seed_document(
        db_session,
        code="LEGAL_TERMS",
        version=1,
        effective_from=datetime.now(timezone.utc) - timedelta(days=1),
    )
    acceptance = LegalAcceptance(
        subject_type=LegalSubjectType.CLIENT,
        subject_id="client-1",
        document_id=doc.id,
        accepted_at=datetime.now(timezone.utc),
    )
    db_session.add(acceptance)
    db_session.commit()
    db_session.refresh(acceptance)

    with pytest.raises(Exception):
        acceptance.subject_id = "client-2"
        db_session.commit()
