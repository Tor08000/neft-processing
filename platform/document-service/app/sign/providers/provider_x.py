from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.settings import get_settings
from app.sign.providers.base import (
    CertificateInfo,
    SignProviderAuthError,
    SignProviderDegradedError,
    SignProviderFailure,
    SignProviderRateLimitError,
    SignProviderTimeoutError,
    SignedResult,
    VerifyResult,
)

settings = get_settings()

_PLACEHOLDER_CREDENTIALS = {"change-me", "changeme", "dev-key", "dev-secret", "test", "dummy", "placeholder"}


def has_real_provider_x_credentials(api_key: str | None, api_secret: str | None) -> bool:
    key = (api_key or "").strip()
    secret = (api_secret or "").strip()
    return bool(key) and bool(secret) and key.lower() not in _PLACEHOLDER_CREDENTIALS and secret.lower() not in _PLACEHOLDER_CREDENTIALS


@dataclass(frozen=True)
class ProviderXConfig:
    base_url: str
    api_key: str
    api_secret: str
    timeout_seconds: float = 15.0


class ProviderX:
    def __init__(self, config: ProviderXConfig | None = None) -> None:
        if config is None:
            config = ProviderXConfig(
                base_url=(settings.provider_x_base_url or "").rstrip("/"),
                api_key=settings.provider_x_api_key,
                api_secret=settings.provider_x_api_secret,
                timeout_seconds=settings.provider_x_timeout_seconds,
            )
        self.config = config

    def sign(self, payload: bytes, meta: dict[str, Any] | None = None) -> SignedResult:
        self._ensure_configured()
        body = {
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "meta": meta or {},
        }
        response = self._request("/sign", body)
        return SignedResult(
            signed_bytes=base64.b64decode(response["signed_base64"]),
            signature_bytes=base64.b64decode(response["signature_base64"]),
            provider_request_id=response.get("request_id"),
            certificate=_parse_certificate(response.get("certificate")),
        )

    def verify(
        self,
        payload: bytes,
        signature: bytes,
        meta: dict[str, Any] | None = None,
    ) -> VerifyResult:
        self._ensure_configured()
        body = {
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "signature_base64": base64.b64encode(signature).decode("ascii"),
            "meta": meta or {},
        }
        response = self._request("/verify", body)
        return VerifyResult(
            verified=bool(response.get("verified", False)),
            error_code=response.get("error_code"),
            certificate=_parse_certificate(response.get("certificate")),
        )

    def _ensure_configured(self) -> None:
        if not self.config.base_url or not has_real_provider_x_credentials(self.config.api_key, self.config.api_secret):
            raise SignProviderDegradedError(
                "Provider X URL and credentials must be configured before live signing",
                code="provider_x_unconfigured",
            )

    def _request(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = _sign_payload(payload, secret=self.config.api_secret, timestamp=timestamp)
        headers = {
            "X-Api-Key": self.config.api_key,
            "X-Request-Timestamp": timestamp,
            "X-Request-Signature": signature,
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.post(f"{self.config.base_url}{path}", content=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise SignProviderTimeoutError("E-sign provider request timed out", code="esign_provider_timeout") from exc
        except httpx.RequestError as exc:
            raise SignProviderFailure(
                "E-sign provider transport failed",
                code="esign_provider_transport_error",
                category="provider_error",
            ) from exc

        if response.status_code in {401, 403}:
            raise SignProviderAuthError("E-sign provider rejected credentials", code="esign_provider_auth_failed")
        if response.status_code == 429:
            raise SignProviderRateLimitError("E-sign provider rate limit reached", code="esign_provider_rate_limited")
        if response.status_code >= 500:
            raise SignProviderFailure(
                "E-sign provider returned server error",
                code=f"esign_provider_http_{response.status_code}",
                category="provider_error",
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SignProviderFailure(
                "E-sign provider rejected request",
                code=f"esign_provider_http_{response.status_code}",
                category="provider_error",
            ) from exc
        return response.json()


class MockProviderX:
    def sign(self, payload: bytes, meta: dict[str, Any] | None = None) -> SignedResult:
        digest = hashlib.sha256(payload).hexdigest()
        signature = f"mock-signature:{digest}".encode("utf-8")
        return SignedResult(
            signed_bytes=payload,
            signature_bytes=signature,
            provider_request_id=f"mock-{digest[:12]}",
            certificate=CertificateInfo(subject="Mock Provider X", valid_to=None),
        )

    def verify(
        self,
        payload: bytes,
        signature: bytes,
        meta: dict[str, Any] | None = None,
    ) -> VerifyResult:
        expected = f"mock-signature:{hashlib.sha256(payload).hexdigest()}".encode("utf-8")
        verified = hmac.compare_digest(signature, expected)
        return VerifyResult(verified=verified, error_code=None if verified else "signature_mismatch")


class DegradedProviderX:
    def sign(self, payload: bytes, meta: dict[str, Any] | None = None) -> SignedResult:
        raise SignProviderDegradedError(
            "Provider X transport is disabled or degraded in document-service",
            code="provider_x_degraded",
        )

    def verify(
        self,
        payload: bytes,
        signature: bytes,
        meta: dict[str, Any] | None = None,
    ) -> VerifyResult:
        raise SignProviderDegradedError(
            "Provider X transport is disabled or degraded in document-service",
            code="provider_x_degraded",
        )


def _sign_payload(payload: bytes, *, secret: str, timestamp: str) -> str:
    key = secret.encode("utf-8")
    message = timestamp.encode("utf-8") + payload
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _parse_certificate(data: dict[str, Any] | None) -> CertificateInfo | None:
    if not data:
        return None
    valid_to = data.get("valid_to")
    parsed_valid_to = None
    if valid_to:
        parsed_valid_to = datetime.fromisoformat(valid_to)
    return CertificateInfo(subject=data.get("subject"), valid_to=parsed_valid_to)


__all__ = ["DegradedProviderX", "MockProviderX", "ProviderX", "ProviderXConfig"]
