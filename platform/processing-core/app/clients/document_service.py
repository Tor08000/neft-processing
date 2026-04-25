from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from app.services.s3_storage import S3Storage
from neft_shared.settings import get_settings

settings = get_settings()


@dataclass(slots=True)
class DocumentServiceRenderClient:
    base_url: str = settings.DOCUMENT_SERVICE_URL.rstrip("/")
    timeout: httpx.Timeout = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.timeout = httpx.Timeout(connect=2.0, read=30.0, write=30.0, pool=2.0)

    def render_pdf(self, *, template_id: str, data: dict, doc_type: str | None = None, version: int = 1) -> bytes:
        started = time.perf_counter()
        last_error: Exception | None = None
        application_id = str(data.get("application_id") or "unknown-application")
        document_type = doc_type or template_id
        payload = {
            "template_code": template_id,
            "variables": data,
            "output_format": "PDF",
            "tenant_id": int(data.get("tenant_id") or 0),
            "client_id": data.get("client_id"),
            "idempotency_key": f"client-onboarding:{application_id}:{document_type}:v{version}:{template_id}",
            "meta": {"source": "processing-core.client-generated-docs"},
            "doc_id": f"{application_id}-{document_type}",
            "doc_type": document_type,
            "version": version,
        }
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}/v1/render", json=payload)
                response.raise_for_status()
                rendered = response.json()
                pdf_bytes = S3Storage(bucket=rendered["bucket"]).get_bytes(rendered["object_key"])
                if pdf_bytes is None:
                    raise RuntimeError("document_service_render_object_missing")
                return pdf_bytes
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_error = exc
                continue
            finally:
                _ = time.perf_counter() - started  # render_duration metric placeholder

        raise RuntimeError("document_service_render_failed") from last_error
