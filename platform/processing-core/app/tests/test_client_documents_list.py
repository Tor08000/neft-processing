from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies.client import client_portal_user
from app.domains.documents.models import DocumentDirection
from app.domains.documents.schemas import DocumentDetailsResponse, DocumentFileOut, DocumentListItem, DocumentsListResponse
from app.main import app
from app.routers.client_documents_v1 import _service


class FakeDocumentsService:
    def __init__(self, items: list[DocumentListItem]):
        self._items = items

    def list_documents(self, *, client_id: str, direction: DocumentDirection, status, q, limit, offset):
        filtered = [item for item in self._items if item.direction == direction.value]
        if q:
            q_lower = q.lower()
            filtered = [
                item
                for item in filtered
                if q_lower in item.title.lower() or (item.number and q_lower in item.number.lower())
            ]
        return DocumentsListResponse(items=filtered[offset : offset + limit], total=len(filtered), limit=limit, offset=offset)

    def get_document(self, *, client_id: str, document_id: str):
        for item in self._items:
            if item.id == document_id:
                if client_id != "client-a":
                    return None
                return DocumentDetailsResponse(
                    id=item.id,
                    client_id=client_id,
                    direction=item.direction,
                    title=item.title,
                    doc_type=item.doc_type,
                    status=item.status,
                    counterparty_name=item.counterparty_name,
                    counterparty_inn=None,
                    number=item.number,
                    date=item.date,
                    amount=item.amount,
                    currency=item.currency,
                    created_at=item.created_at,
                    updated_at=item.created_at,
                    files=[
                        DocumentFileOut(
                            id="f1",
                            filename="doc.pdf",
                            mime="application/pdf",
                            size=1,
                            sha256=None,
                            created_at=item.created_at,
                        )
                    ],
                )
        return None


def _doc(doc_id: str, direction: str, title: str, number: str | None = None) -> DocumentListItem:
    return DocumentListItem(
        id=doc_id,
        direction=direction,
        title=title,
        doc_type="AGREEMENT",
        status="DRAFT",
        counterparty_name="ООО Тест",
        number=number,
        date=None,
        amount=None,
        currency=None,
        created_at=datetime.now(timezone.utc),
        files_count=0,
    )


def test_list_documents_empty_returns_200(make_jwt):
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")
    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    app.dependency_overrides[_service] = lambda: FakeDocumentsService([])
    try:
        with TestClient(app) as api_client:
            response = api_client.get(
                "/api/core/client/documents?direction=inbound",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0
    finally:
        app.dependency_overrides.clear()


def test_list_documents_acl_other_client_hidden(make_jwt):
    docs = [_doc("doc-1", "INBOUND", "Договор 1", "A-1")]

    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-b"}
    app.dependency_overrides[_service] = lambda: FakeDocumentsService(docs)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-b")

    try:
        with TestClient(app) as api_client:
            list_response = api_client.get(
                "/api/core/client/documents?direction=inbound",
                headers={"Authorization": f"Bearer {token}"},
            )
            detail_response = api_client.get(
                "/api/core/client/documents/doc-1",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert list_response.status_code == 200
        assert list_response.json()["items"] == []
        assert detail_response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_filters_work_no_error(make_jwt):
    docs = [
        _doc("doc-1", "INBOUND", "Договор поставки", "A-1"),
        _doc("doc-2", "INBOUND", "Счет на оплату", "B-2"),
    ]

    app.dependency_overrides[client_portal_user] = lambda: {"client_id": "client-a"}
    app.dependency_overrides[_service] = lambda: FakeDocumentsService(docs)
    token = make_jwt(roles=("CLIENT_USER",), client_id="client-a")

    try:
        with TestClient(app) as api_client:
            response = api_client.get(
                "/api/core/client/documents?direction=inbound&q=поставки",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["id"] == "doc-1"
    finally:
        app.dependency_overrides.clear()
