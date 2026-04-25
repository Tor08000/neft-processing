import hashlib
import os
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.domains.documents.models  # noqa: F401 - keep merged document registry aligned with runtime
import app.routers.client_documents as client_documents_router
import app.services.abac.dependency as abac_dependency
import app.services.closing_documents as closing_documents
from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.client import client_portal_user
from app.db import Base, get_db
from app.models.audit_log import AuditLog
from app.models.documents import ClosingPackage, Document, DocumentFile
from app.models.finance import CreditNote, InvoicePayment
from app.models.invoice import Invoice, InvoiceStatus
from app.routers.admin.closing_packages import router as admin_closing_packages_router
from app.routers.client_documents import router as client_documents_router_def
from app.services.abac.dependency import get_abac_principal
from app.services.abac.engine import AbacDecision, AbacPrincipal
from app.services.documents_storage import DocumentsStorage as RealDocumentsStorage
from app.services.documents_storage import StoredDocumentFile

os.environ.setdefault("DISABLE_CELERY", "1")


def _dedupe_table_indexes(*tables) -> None:
    for table in tables:
        seen: set[tuple[str | None, tuple[str, ...]]] = set()
        for index in list(table.indexes):
            signature = (index.name, tuple(column.name for column in index.columns))
            if signature in seen:
                table.indexes.remove(index)
            else:
                seen.add(signature)


class _NoopGraphBuilder:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def ensure_document_graph(self, *args, **kwargs) -> None:
        return None

    def ensure_closing_package_graph(self, *args, **kwargs) -> None:
        return None


class _MemoryDocumentsStorage:
    _objects: dict[str, bytes] = {}

    def __init__(self) -> None:
        self.bucket = "test-documents"

    @staticmethod
    def build_object_key(**kwargs):
        return RealDocumentsStorage.build_object_key(**kwargs)

    @classmethod
    def reset(cls) -> None:
        cls._objects = {}

    def store_bytes(
        self,
        *,
        object_key: str,
        payload: bytes,
        content_type: str,
    ) -> StoredDocumentFile:
        self._objects[object_key] = payload
        return StoredDocumentFile(
            bucket=self.bucket,
            object_key=object_key,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            content_type=content_type,
        )

    def fetch_bytes(self, object_key: str) -> bytes | None:
        return self._objects.get(object_key)

    def exists(self, object_key: str) -> bool:
        return object_key in self._objects


@pytest.fixture()
def closing_documents_context(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(closing_documents.settings, "DOCUMENT_SERVICE_ENABLED", False, raising=False)
    monkeypatch.setattr(closing_documents, "LegalGraphBuilder", _NoopGraphBuilder)
    monkeypatch.setattr(closing_documents, "DocumentsStorage", _MemoryDocumentsStorage)
    monkeypatch.setattr(client_documents_router, "DocumentsStorage", _MemoryDocumentsStorage)
    monkeypatch.setattr(
        client_documents_router,
        "evaluate_with_db",
        lambda *_args, **_kwargs: (client_documents_router.UnifiedRulePolicy.ALLOW, [], None),
    )
    monkeypatch.setattr(
        abac_dependency.AbacEngine,
        "evaluate",
        lambda self, **_kwargs: AbacDecision(
            allowed=True,
            reason_code=None,
            matched_policies=[],
            explain={"result": True, "policy": "test-allow"},
        ),
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if "clearing_batch" not in Base.metadata.tables:
        Table("clearing_batch", Base.metadata, Column("id", String(36), primary_key=True), extend_existing=True)
    if "billing_periods" not in Base.metadata.tables:
        Table("billing_periods", Base.metadata, Column("id", String(36), primary_key=True), extend_existing=True)
    if "reconciliation_requests" not in Base.metadata.tables:
        Table(
            "reconciliation_requests",
            Base.metadata,
            Column("id", String(36), primary_key=True),
            extend_existing=True,
        )

    _dedupe_table_indexes(DocumentFile.__table__)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Invoice.__table__,
            InvoicePayment.__table__,
            CreditNote.__table__,
            Document.__table__,
            DocumentFile.__table__,
            ClosingPackage.__table__,
            AuditLog.__table__,
        ],
    )

    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    auth_state = {
        "admin": {
            "sub": "admin@neft.local",
            "user_id": "admin-1",
            "roles": ["ADMIN"],
            "role": "ADMIN",
            "tenant_id": 1,
        },
        "client": {
            "sub": "client@neft.local",
            "user_id": "client-user-1",
            "client_id": "client-1",
            "roles": ["CLIENT_USER"],
            "role": "CLIENT_USER",
            "tenant_id": 1,
            "email": "client@neft.local",
        },
    }

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def admin_override():
        return dict(auth_state["admin"])

    def client_override():
        return dict(auth_state["client"])

    def abac_principal_override():
        return AbacPrincipal(
            type="CLIENT",
            user_id=str(auth_state["client"].get("user_id")),
            client_id=str(auth_state["client"].get("client_id")),
            partner_id=None,
            service_name=None,
            roles={"CLIENT_USER"},
            scopes=set(),
            region=None,
            raw=dict(auth_state["client"]),
        )

    local_app = FastAPI()
    local_app.include_router(admin_closing_packages_router, prefix="/api/v1/admin")
    local_app.include_router(client_documents_router_def)
    local_app.dependency_overrides[get_db] = override_get_db
    local_app.dependency_overrides[require_admin_user] = admin_override
    local_app.dependency_overrides[client_portal_user] = client_override
    local_app.dependency_overrides[get_abac_principal] = abac_principal_override

    _MemoryDocumentsStorage.reset()
    try:
        with TestClient(local_app, headers={"Authorization": "Bearer test-token"}) as api_client:
            yield session_factory, api_client, auth_state
    finally:
        local_app.dependency_overrides.clear()
        _MemoryDocumentsStorage.reset()
        engine.dispose()


def _seed_invoice(
    session_factory: sessionmaker[Session],
    *,
    client_id: str,
    period_from: date,
    period_to: date,
) -> str:
    session = session_factory()
    try:
        invoice_id = str(uuid4())
        invoice = Invoice(
            id=invoice_id,
            client_id=client_id,
            number=f"INV-{invoice_id[:8]}",
            period_from=period_from,
            period_to=period_to,
            currency="RUB",
            status=InvoiceStatus.SENT,
            total_amount=10000,
            tax_amount=2000,
            total_with_tax=12000,
            amount_paid=5000,
            amount_due=7000,
            amount_refunded=0,
            issued_at=datetime.now(timezone.utc),
        )
        session.add(invoice)
        session.add(
            InvoicePayment(
                id=str(uuid4()),
                invoice_id=invoice_id,
                amount=5000,
                currency="RUB",
                idempotency_key=f"pay-{invoice_id}",
            )
        )
        session.add(
            CreditNote(
                id=str(uuid4()),
                invoice_id=invoice_id,
                amount=1000,
                currency="RUB",
                idempotency_key=f"refund-{invoice_id}",
            )
        )
        session.commit()
        return invoice_id
    finally:
        session.close()


def _generate_package(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/v1/admin/closing-packages/generate", json=payload)
    assert response.status_code == 200
    return response.json()


def test_closing_package_generate_and_download_e2e(closing_documents_context):
    session_factory, api_client, auth_state = closing_documents_context
    period_from = date(2025, 12, 1)
    period_to = date(2025, 12, 31)
    client_id = "client-1"
    auth_state["client"]["client_id"] = client_id
    _seed_invoice(session_factory, client_id=client_id, period_from=period_from, period_to=period_to)

    payload = {
        "client_id": client_id,
        "date_from": period_from.isoformat(),
        "date_to": period_to.isoformat(),
        "version_mode": "AUTO",
        "force_new_version": False,
        "tenant_id": 1,
    }

    result = _generate_package(api_client, payload)
    assert result["version"] == 1
    assert len(result["documents"]) == 3

    session = session_factory()
    try:
        documents = session.query(Document).all()
        files = session.query(DocumentFile).all()
        assert len(documents) == 3
        assert len(files) == 6

        storage = _MemoryDocumentsStorage()
        for document in documents:
            for file in document.files:
                assert storage.exists(file.object_key)

            pdf_resp = api_client.get(
                f"/api/v1/client/documents/{document.id}/download",
                params={"file_type": "PDF"},
            )
            assert pdf_resp.status_code == 200
            assert pdf_resp.headers["content-type"] == "application/pdf"
            assert len(pdf_resp.content) > 0

            xlsx_resp = api_client.get(
                f"/api/v1/client/documents/{document.id}/download",
                params={"file_type": "XLSX"},
            )
            assert xlsx_resp.status_code == 200
            assert (
                xlsx_resp.headers["content-type"]
                == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            assert len(xlsx_resp.content) > 0
    finally:
        session.close()


def test_versioning_regeneration(closing_documents_context):
    session_factory, api_client, auth_state = closing_documents_context
    period_from = date(2025, 11, 1)
    period_to = date(2025, 11, 30)
    client_id = "client-2"
    auth_state["client"]["client_id"] = client_id
    _seed_invoice(session_factory, client_id=client_id, period_from=period_from, period_to=period_to)

    payload = {
        "client_id": client_id,
        "date_from": period_from.isoformat(),
        "date_to": period_to.isoformat(),
        "version_mode": "AUTO",
        "force_new_version": False,
        "tenant_id": 1,
    }

    first = _generate_package(api_client, payload)
    second = _generate_package(api_client, payload)
    assert first["package_id"] == second["package_id"]
    assert first["version"] == second["version"] == 1

    payload["force_new_version"] = True
    third = _generate_package(api_client, payload)
    assert third["version"] == 2

    session = session_factory()
    try:
        documents = session.query(Document).filter(Document.client_id == client_id).all()
        versions = {doc.version for doc in documents}
        assert versions == {1, 2}

        storage = _MemoryDocumentsStorage()
        for document in documents:
            for file in document.files:
                assert storage.exists(file.object_key)
    finally:
        session.close()


def test_client_scope_protection(closing_documents_context):
    session_factory, api_client, auth_state = closing_documents_context
    period_from = date(2025, 10, 1)
    period_to = date(2025, 10, 31)
    client_id = "client-3"
    other_client = "client-4"
    auth_state["client"]["client_id"] = client_id
    _seed_invoice(session_factory, client_id=client_id, period_from=period_from, period_to=period_to)

    payload = {
        "client_id": client_id,
        "date_from": period_from.isoformat(),
        "date_to": period_to.isoformat(),
        "version_mode": "AUTO",
        "force_new_version": False,
        "tenant_id": 1,
    }

    result = _generate_package(api_client, payload)
    document_id = result["documents"][0]["id"]
    auth_state["client"]["client_id"] = other_client

    resp = api_client.get(
        f"/api/v1/client/documents/{document_id}/download",
        params={"file_type": "PDF"},
    )
    assert resp.status_code == 403
