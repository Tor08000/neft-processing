from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from neft_integration_hub.providers.base import ProviderStatus
from neft_integration_hub.settings import get_settings

settings = get_settings()


@dataclass
class MockDiadokProvider:
    delivery_seconds: int = 5
    sign_seconds: int = 12

    def send(self, document_bytes: bytes, meta: dict) -> str:
        timestamp = int(time.time())
        return f"mock-diadok-{timestamp}"

    def poll(self, provider_message_id: str) -> ProviderStatus:
        try:
            issued_at = int(provider_message_id.rsplit("-", 1)[-1])
        except (ValueError, IndexError):
            return ProviderStatus(status="FAILED", error_code="invalid_message_id", error_message="Bad ID")

        elapsed = int(time.time()) - issued_at
        if elapsed >= self.sign_seconds:
            return ProviderStatus(status="SIGNED_BY_COUNTERPARTY")
        if elapsed >= self.delivery_seconds:
            return ProviderStatus(status="DELIVERED")
        return ProviderStatus(status="SENT")

    def download_signed(self, provider_message_id: str) -> bytes | None:
        return None


@dataclass
class ProdDiadokProvider:
    base_url: str = settings.diadok_base_url
    api_token: str = settings.diadok_api_token
    timeout_seconds: int = settings.diadok_timeout_seconds

    def send(self, document_bytes: bytes, meta: dict) -> str:
        payload = json.dumps(
            {"document": base64.b64encode(document_bytes).decode("utf-8"), "meta": meta},
            ensure_ascii=False,
        ).encode("utf-8")
        response = self._request("POST", "/send", payload)
        return response.get("message_id", response.get("id", ""))

    def poll(self, provider_message_id: str) -> ProviderStatus:
        response = self._request("GET", f"/status/{provider_message_id}", None)
        status = response.get("status", "FAILED")
        error_code = response.get("error_code")
        error_message = response.get("error_message")
        return ProviderStatus(status=status, error_code=error_code, error_message=error_message)

    def download_signed(self, provider_message_id: str) -> bytes | None:
        return self._request("GET", f"/signed/{provider_message_id}", None, expect_json=False)

    def _request(self, method: str, path: str, payload: bytes | None, expect_json: bool = True):
        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        url = f"{self.base_url}{path}"
        try:
            request = Request(url, data=payload, headers=headers, method=method)
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read()
            if not expect_json:
                return data
            return json.loads(data.decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"diadok_http_error:{exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("diadok_unavailable") from exc


__all__ = ["MockDiadokProvider", "ProdDiadokProvider"]
