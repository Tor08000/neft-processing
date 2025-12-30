from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class CertificateInfo:
    subject: str | None = None
    valid_to: datetime | None = None


@dataclass(frozen=True)
class SignedResult:
    signed_bytes: bytes
    signature_bytes: bytes
    provider_request_id: str | None = None
    certificate: CertificateInfo | None = None


@dataclass(frozen=True)
class VerifyResult:
    verified: bool
    error_code: str | None = None
    certificate: CertificateInfo | None = None


class SignProvider(Protocol):
    def sign(self, payload: bytes, meta: dict[str, Any] | None = None) -> SignedResult:
        raise NotImplementedError

    def verify(
        self,
        payload: bytes,
        signature: bytes,
        meta: dict[str, Any] | None = None,
    ) -> VerifyResult:
        raise NotImplementedError


__all__ = ["CertificateInfo", "SignedResult", "VerifyResult", "SignProvider"]
