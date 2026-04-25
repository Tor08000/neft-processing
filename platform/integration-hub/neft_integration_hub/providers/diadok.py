from __future__ import annotations

import base64
import json
import socket
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from neft_integration_hub.providers.base import (
    ProviderAuthError,
    ProviderDegradedError,
    ProviderFailure,
    ProviderStatus,
    ProviderTimeoutError,
)
from neft_integration_hub.settings import get_settings

settings = get_settings()

_PLACEHOLDER_SECRETS = {"change-me", "changeme", "dev-key", "dev-secret", "test", "dummy", "placeholder"}
_PLACEHOLDER_URLS = {"https://diadok.example.com", "http://diadok.example.com"}


def _real_secret(value: str | None) -> bool:
    normalized = (value or "").strip()
    return bool(normalized) and normalized.lower() not in _PLACEHOLDER_SECRETS


def _real_provider_url(value: str | None) -> bool:
    normalized = (value or "").strip().rstrip("/")
    return bool(normalized) and normalized.lower() not in _PLACEHOLDER_URLS


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
class MockSbisProvider(MockDiadokProvider):
    def send(self, document_bytes: bytes, meta: dict) -> str:
        timestamp = int(time.time())
        return f"sandbox-sbis-{timestamp}"


@dataclass
class UnavailableDiadokProvider:
    mode: str
    provider: str = "DIADOK"

    def _raise(self) -> None:
        provider_label = self.provider.upper()
        raise ProviderDegradedError(
            f"{provider_label} provider is {self.mode}",
            code=f"{provider_label.lower()}_{self.mode}",
            provider=provider_label,
        )

    def send(self, document_bytes: bytes, meta: dict) -> str:
        self._raise()

    def poll(self, provider_message_id: str) -> ProviderStatus:
        self._raise()

    def download_signed(self, provider_message_id: str) -> bytes | None:
        self._raise()


@dataclass
class ProdDiadokProvider:
    base_url: str = settings.diadok_base_url
    api_token: str = settings.diadok_api_token
    timeout_seconds: int = settings.diadok_timeout_seconds

    def send(self, document_bytes: bytes, meta: dict) -> str:
        if not _real_provider_url(self.base_url) or not _real_secret(self.api_token):
            raise ProviderDegradedError(
                "Diadok base URL or API token is not configured",
                code="diadok_unconfigured",
                provider="DIADOK",
            )
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
            if exc.code in {401, 403}:
                raise ProviderAuthError(
                    "Diadok authentication failed",
                    code=f"diadok_http_{exc.code}",
                    provider="DIADOK",
                ) from exc
            raise ProviderFailure(
                f"Diadok returned HTTP {exc.code}",
                code=f"diadok_http_{exc.code}",
                error_type="provider_error",
                retryable=exc.code >= 500,
                provider="DIADOK",
            ) from exc
        except socket.timeout as exc:
            raise ProviderTimeoutError("Diadok request timed out", code="diadok_timeout", provider="DIADOK") from exc
        except TimeoutError as exc:
            raise ProviderTimeoutError("Diadok request timed out", code="diadok_timeout", provider="DIADOK") from exc
        except URLError as exc:
            raise ProviderFailure(
                "Diadok transport is unavailable",
                code="diadok_unavailable",
                error_type="provider_error",
                retryable=True,
                provider="DIADOK",
            ) from exc


__all__ = ["MockDiadokProvider", "MockSbisProvider", "ProdDiadokProvider", "UnavailableDiadokProvider"]
