from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.api.dependencies.admin import require_admin_user
from app.models.audit_log import AuditLog
from app.models.legal_acceptance import LegalAcceptance
from app.models.legal_document import LegalDocument, LegalDocumentContentType, LegalDocumentStatus
from app.routers.admin.legal import router as legal_router
from app.tests._scoped_router_harness import router_client_context, scoped_session_context

LEGAL_ADMIN_TEST_TABLES = (
    AuditLog.__table__,
    LegalDocument.__table__,
    LegalAcceptance.__table__,
)


def _admin_claims(*roles: str) -> dict[str, object]:
    return {
        "user_id": "admin-legal-1",
        "sub": "admin-legal-1",
        "email": "legal@example.com",
        "roles": list(roles),
    }


def test_admin_legal_documents_registry_uses_canonical_legal_owner() -> None:
    with scoped_session_context(tables=LEGAL_ADMIN_TEST_TABLES) as session:
        session.add(
            LegalDocument(
                id=str(uuid4()),
                code="TERMS",
                version="2",
                title="Terms v2",
                locale="ru",
                effective_from=datetime.now(timezone.utc) - timedelta(days=1),
                status=LegalDocumentStatus.PUBLISHED,
                content_type=LegalDocumentContentType.MARKDOWN,
                content="updated",
                content_hash="hash-terms-v2",
                published_at=datetime.now(timezone.utc) - timedelta(hours=2),
            )
        )
        session.commit()

        with router_client_context(
            router=legal_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("NEFT_LEGAL")},
        ) as client:
            response = client.get("/api/core/v1/admin/legal/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["code"] == "TERMS"
    assert payload["items"][0]["status"] == "PUBLISHED"


def test_admin_legal_documents_registry_allows_support_read_but_denies_operate() -> None:
    with scoped_session_context(tables=LEGAL_ADMIN_TEST_TABLES) as session:
        session.add(
            LegalDocument(
                id=str(uuid4()),
                code="POLICY",
                version="1",
                title="Policy v1",
                locale="ru",
                effective_from=datetime.now(timezone.utc) - timedelta(days=1),
                status=LegalDocumentStatus.DRAFT,
                content_type=LegalDocumentContentType.MARKDOWN,
                content="policy",
                content_hash="hash-policy-v1",
            )
        )
        session.commit()

        with router_client_context(
            router=legal_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("NEFT_SUPPORT")},
        ) as client:
            read_response = client.get("/api/core/v1/admin/legal/documents")
            write_response = client.post(
                "/api/core/v1/admin/legal/documents",
                json={
                    "code": "POLICY",
                    "version": "2",
                    "title": "Policy v2",
                    "locale": "ru",
                    "effective_from": datetime.now(timezone.utc).isoformat(),
                    "content_type": "MARKDOWN",
                    "content": "updated",
                },
            )

    assert read_response.status_code == 200
    assert write_response.status_code == 403
    assert write_response.json()["detail"] == "forbidden_admin_role"


def test_admin_legal_registry_returns_empty_when_legal_tables_are_not_bootstrapped() -> None:
    with scoped_session_context(tables=()) as session:
        with router_client_context(
            router=legal_router,
            prefix="/api/core/v1/admin",
            db_session=session,
            dependency_overrides={require_admin_user: lambda: _admin_claims("NEFT_LEGAL")},
        ) as client:
            documents_response = client.get("/api/core/v1/admin/legal/documents")
            acceptances_response = client.get("/api/core/v1/admin/legal/acceptances")
            partners_response = client.get("/api/core/v1/admin/legal/partners-legacy")

    assert documents_response.status_code == 200
    assert documents_response.json() == {"items": []}
    assert acceptances_response.status_code == 200
    assert acceptances_response.json() == {"items": []}
    assert partners_response.status_code == 200
    assert partners_response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0, "cursor": None}
