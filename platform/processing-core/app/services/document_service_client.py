from __future__ import annotations

from dataclasses import dataclass

import httpx

from neft_shared.settings import get_settings

settings = get_settings()


@dataclass(frozen=True)
class DocumentRenderRequest:
    template_kind: str
    template_id: str | None
    template_html: str
    data: dict
    output_format: str
    tenant_id: int
    client_id: str | None
    idempotency_key: str
    meta: dict | None
    doc_id: str
    doc_type: str
    version: int
    document_date: str | None


@dataclass(frozen=True)
class DocumentRenderResult:
    bucket: str
    object_key: str
    sha256: str
    size_bytes: int
    content_type: str
    version: int


class DocumentServiceClient:
    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.DOCUMENT_SERVICE_URL).rstrip("/")
        self.timeout = httpx.Timeout(connect=2.0, read=30.0, write=30.0, pool=2.0)

    def render(self, request: DocumentRenderRequest) -> DocumentRenderResult:
        payload = {
            "template_kind": request.template_kind,
            "template_id": request.template_id,
            "template_html": request.template_html,
            "data": request.data,
            "output_format": request.output_format,
            "tenant_id": request.tenant_id,
            "client_id": request.client_id,
            "idempotency_key": request.idempotency_key,
            "meta": request.meta,
            "doc_id": request.doc_id,
            "doc_type": request.doc_type,
            "version": request.version,
            "document_date": request.document_date,
        }

        last_error: Exception | None = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}/v1/render", json=payload)
                response.raise_for_status()
                data = response.json()
                return DocumentRenderResult(
                    bucket=data["bucket"],
                    object_key=data["object_key"],
                    sha256=data["sha256"],
                    size_bytes=int(data["size_bytes"]),
                    content_type=data["content_type"],
                    version=int(data["version"]),
                )
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise RuntimeError("document_service_render_failed") from exc

        raise RuntimeError("document_service_unreachable") from last_error


__all__ = ["DocumentServiceClient", "DocumentRenderRequest", "DocumentRenderResult"]
