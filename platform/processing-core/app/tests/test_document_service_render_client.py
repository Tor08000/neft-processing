from __future__ import annotations

import httpx

from app.clients.document_service import DocumentServiceRenderClient


def test_document_service_render_client_initializes_timeout_with_slots() -> None:
    client = DocumentServiceRenderClient(base_url="http://document-service:8000")

    assert client.base_url == "http://document-service:8000"
    assert isinstance(client.timeout, httpx.Timeout)


def test_document_service_render_client_uses_canonical_render_contract(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"bucket": "neft-documents", "object_key": "documents/doc-1.pdf"}

    class _HttpClient:
        def __init__(self, *, timeout: httpx.Timeout) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> "_HttpClient":
            return self

        def __exit__(self, *_args) -> None:
            return None

        def post(self, url: str, *, json: dict) -> _Response:
            captured["url"] = url
            captured["payload"] = json
            return _Response()

    class _Storage:
        def __init__(self, *, bucket: str) -> None:
            captured["bucket"] = bucket

        def get_bytes(self, key: str) -> bytes:
            captured["object_key"] = key
            return b"%PDF-1.7 rendered"

    monkeypatch.setattr("app.clients.document_service.httpx.Client", _HttpClient)
    monkeypatch.setattr("app.clients.document_service.S3Storage", _Storage)

    client = DocumentServiceRenderClient(base_url="http://document-service:8000")
    result = client.render_pdf(
        template_id="offer_v1",
        data={"application_id": "app-1", "company_name": "ACME", "client_id": "client-1"},
        doc_type="OFFER",
        version=2,
    )

    assert result == b"%PDF-1.7 rendered"
    assert captured["url"] == "http://document-service:8000/v1/render"
    assert captured["bucket"] == "neft-documents"
    assert captured["object_key"] == "documents/doc-1.pdf"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["template_code"] == "offer_v1"
    assert payload["doc_type"] == "OFFER"
    assert payload["version"] == 2
    assert payload["idempotency_key"] == "client-onboarding:app-1:OFFER:v2:offer_v1"
