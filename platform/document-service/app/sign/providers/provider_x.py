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
from app.sign.providers.base import CertificateInfo, SignedResult, VerifyResult

settings = get_settings()


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
        if not self.config.base_url:
            raise RuntimeError("provider_x_unconfigured")
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
        if not self.config.base_url:
            raise RuntimeError("provider_x_unconfigured")
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
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(f"{self.config.base_url}{path}", content=payload, headers=headers)
        response.raise_for_status()
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


__all__ = ["ProviderX", "MockProviderX", "ProviderXConfig"]
