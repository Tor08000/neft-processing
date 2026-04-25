from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin, require_admin_user
from app.db import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.legal_acceptance import LegalAcceptance, LegalAcceptanceImmutableError, LegalSubjectType
from app.models.legal_document import LegalDocument, LegalDocumentContentType, LegalDocumentStatus
from app.security.rbac.principal import Principal, get_portal_principal, get_principal
from app.services import legal as legal_service
from app.services.legal import LegalService, subject_from_request


ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    AuditLog.__table__.create(bind=engine)
    LegalDocument.__table__.create(bind=engine)
    LegalAcceptance.__table__.create(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        LegalAcceptance.__table__.drop(bind=engine)
        LegalDocument.__table__.drop(bind=engine)
        AuditLog.__table__.drop(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    def _override_db():
        try:
            yield db_session
        finally:
            pass

    def _override_admin():
        return {"roles": ["SUPERADMIN"], "user_id": ADMIN_USER_ID}

    def _override_admin_user(request: Request):
        token = _override_admin()
        subject = subject_from_request(subject_type=LegalSubjectType.USER, subject_id=ADMIN_USER_ID)
        legal_service.enforce_legal_gate(
            db=db_session,
            request=request,
            subject=subject,
            actor_roles=token["roles"],
        )
        return token

    def _override_principal():
        return Principal(
            user_id=UUID(ADMIN_USER_ID),
            roles={"admin"},
            scopes=set(),
            client_id=None,
            partner_id=None,
            is_admin=True,
            raw_claims={"user_id": ADMIN_USER_ID, "sub": ADMIN_USER_ID, "roles": ["SUPERADMIN"]},
        )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_admin] = _override_admin
    app.dependency_overrides[require_admin_user] = _override_admin_user
    app.dependency_overrides[get_principal] = _override_principal
    app.dependency_overrides[get_portal_principal] = _override_principal

    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS_IN_PROD", "1")
    legal_service.settings.LEGAL_GATE_ENABLED = True
    legal_service.settings.LEGAL_REQUIRED_DOCS = "TERMS"
    legal_service.settings.LEGAL_GATE_EXEMPT_ROLES = ""

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(require_admin_user, None)
    app.dependency_overrides.pop(get_principal, None)
    app.dependency_overrides.pop(get_portal_principal, None)


@pytest.fixture()
def seeded_document(db_session: Session) -> LegalDocument:
    service = LegalService(db_session)
    document = LegalDocument(
        id=str(uuid4()),
        code="TERMS",
        version="1",
        title="Terms",
        locale="ru",
        effective_from=datetime.now(timezone.utc) - timedelta(days=1),
        status=LegalDocumentStatus.PUBLISHED,
        content_type=LegalDocumentContentType.MARKDOWN,
        content="TBD",
        content_hash=service.compute_content_hash("TBD"),
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(document)
    db_session.commit()
    return document


def test_legal_gate_blocks_protected_action(client: TestClient, seeded_document: LegalDocument):
    response = client.post(
        "/api/core/v1/admin/legal/documents",
        json={
            "code": "SMOKE",
            "version": "1",
            "title": "Smoke",
            "locale": "ru",
            "effective_from": datetime.now(timezone.utc).isoformat(),
            "content_type": "MARKDOWN",
            "content": "TBD",
        },
    )
    assert response.status_code == 428
    assert response.json()["error"]["code"] == "LEGAL_REQUIRED"


def test_legal_gate_allows_after_acceptance(client: TestClient, db_session: Session, seeded_document: LegalDocument):
    accept_response = client.post(
        "/api/legal/accept",
        json={"code": "TERMS", "version": "1", "locale": "ru", "accepted": True},
    )
    assert accept_response.status_code == 204

    response = client.post(
        "/api/core/v1/admin/legal/documents",
        json={
            "code": "SMOKE",
            "version": "1",
            "title": "Smoke",
            "locale": "ru",
            "effective_from": datetime.now(timezone.utc).isoformat(),
            "content_type": "MARKDOWN",
            "content": "TBD",
        },
    )
    assert response.status_code == 200


def test_acceptance_is_immutable(db_session: Session, seeded_document: LegalDocument):
    subject = subject_from_request(subject_type=LegalSubjectType.USER, subject_id="user-1")
    service = LegalService(db_session)
    acceptance = service.accept_document(
        subject=subject,
        document=seeded_document,
        ip="127.0.0.1",
        user_agent="pytest",
        signature=None,
        meta=None,
        request_ctx=None,
    )
    db_session.commit()

    acceptance.ip = "10.0.0.1"
    with pytest.raises(LegalAcceptanceImmutableError):
        db_session.commit()


def test_required_picks_latest_published(db_session: Session):
    service = LegalService(db_session)
    now = datetime.now(timezone.utc)
    doc_old = LegalDocument(
        id=str(uuid4()),
        code="TERMS",
        version="1",
        title="Old",
        locale="ru",
        effective_from=now - timedelta(days=10),
        status=LegalDocumentStatus.PUBLISHED,
        content_type=LegalDocumentContentType.MARKDOWN,
        content="old",
        content_hash=service.compute_content_hash("old"),
        published_at=now - timedelta(days=9),
    )
    doc_new = LegalDocument(
        id=str(uuid4()),
        code="TERMS",
        version="2",
        title="New",
        locale="ru",
        effective_from=now - timedelta(days=1),
        status=LegalDocumentStatus.PUBLISHED,
        content_type=LegalDocumentContentType.MARKDOWN,
        content="new",
        content_hash=service.compute_content_hash("new"),
        published_at=now - timedelta(hours=2),
    )
    db_session.add_all([doc_old, doc_new])
    db_session.commit()

    subject = subject_from_request(subject_type=LegalSubjectType.USER, subject_id="user-1")
    required = service.required_documents(subject=subject, required_codes=["TERMS"])
    assert required[0]["required_version"] == "2"
