from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from neft_shared.settings import get_settings

settings = get_settings()


@dataclass(slots=True)
class DocumentServiceRenderClient:
    base_url: str = settings.DOCUMENT_SERVICE_URL.rstrip("/")

    def __post_init__(self) -> None:
        self.timeout = httpx.Timeout(connect=2.0, read=30.0, write=30.0, pool=2.0)

    def render_pdf(self, *, template_id: str, data: dict) -> bytes:
        started = time.perf_counter()
        last_error: Exception | None = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}/api/docs/v1/render", json={"template_id": template_id, "data": data})
                response.raise_for_status()
                return response.content
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_error = exc
                continue
            finally:
                _ = time.perf_counter() - started  # render_duration metric placeholder

        raise RuntimeError("document_service_render_failed") from last_error
