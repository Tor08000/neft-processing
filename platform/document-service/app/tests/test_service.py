from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

import app.main as main
from app.renderer import HtmlRenderResult
from app.schemas import RenderRequest
from app.storage import StoredObjectMetadata


class DummyStorage:
    def __init__(self) -> None:
        self.bucket = "neft-docs"
        self._payloads: dict[str, bytes] = {}
        self._metadata: dict[str, dict[str, str]] = {}

    def ensure_bucket(self) -> None:
        return None

    def put_bytes(self, object_key: str, payload: bytes, *, content_type: str, metadata: dict[str, str] | None = None) -> None:
        self._payloads[object_key] = payload
        self._metadata[object_key] = metadata or {}

    def head_object(self, object_key: str):
        if object_key not in self._payloads:
            return None
        payload = self._payloads[object_key]
        metadata = self._metadata.get(object_key, {})
        return StoredObjectMetadata(
            bucket=self.bucket,
            object_key=object_key,
            size_bytes=len(payload),
            content_type="application/pdf",
            sha256=metadata.get("sha256"),
        )

    def get_bytes(self, object_key: str) -> bytes | None:
        return self._payloads.get(object_key)


class DummyRenderer:
    def __init__(self) -> None:
        self.calls = 0

    def render(self, template_html: str, data: dict):
        self.calls += 1
        payload = f"PDF:{template_html}:{data}".encode("utf-8")
        return HtmlRenderResult(html=template_html, pdf_bytes=payload)


def _build_payload() -> RenderRequest:
    return RenderRequest(
        template_kind="HTML",
        template_id="invoice_v1",
        template_html="<html><body>Hello {{ name }}</body></html>",
        data={"name": "Neft"},
        output_format="PDF",
        tenant_id=1,
        client_id="client-1",
        idempotency_key="idem-1",
        meta={"source": "tests", "doc_type": "INVOICE"},
        doc_id="doc-123",
        doc_type="INVOICE",
        version=1,
    )


def test_health() -> None:
    client = TestClient(main.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "document-service"


def test_metrics() -> None:
    client = TestClient(main.app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "document_service_up 1" in response.text


def test_render_creates_pdf_and_metadata(monkeypatch) -> None:
    storage = DummyStorage()
    renderer = DummyRenderer()

    monkeypatch.setattr(main, "get_storage", lambda: storage)
    monkeypatch.setattr(main, "get_renderer", lambda: renderer)

    client = TestClient(main.app)
    payload = _build_payload()
    response = client.post("/v1/render", json=payload.model_dump())

    assert response.status_code == 200
    body = response.json()
    assert body["bucket"] == "neft-docs"
    assert body["content_type"] == "application/pdf"
    assert body["object_key"].startswith("documents/tenant-1/INVOICE/")
    assert body["object_key"].endswith("/doc-123/v1.pdf")
    assert body["version"] == 1
    assert renderer.calls == 1

    payload_bytes = storage.get_bytes(body["object_key"])
    assert payload_bytes is not None
    assert body["size_bytes"] == len(payload_bytes)
    assert body["sha256"] == hashlib.sha256(payload_bytes).hexdigest()


def test_render_idempotent(monkeypatch) -> None:
    storage = DummyStorage()
    renderer = DummyRenderer()

    monkeypatch.setattr(main, "get_storage", lambda: storage)
    monkeypatch.setattr(main, "get_renderer", lambda: renderer)

    client = TestClient(main.app)
    payload = _build_payload()

    first = client.post("/v1/render", json=payload.model_dump())
    assert first.status_code == 200
    second = client.post("/v1/render", json=payload.model_dump())
    assert second.status_code == 200
    assert first.json() == second.json()
    assert renderer.calls == 1
