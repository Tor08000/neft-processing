from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


class SignProviderFailure(RuntimeError):
    def __init__(self, message: str, *, code: str = "sign_provider_failure", category: str = "provider_error") -> None:
        super().__init__(message)
        self.code = code
        self.category = category


class SignProviderDegradedError(SignProviderFailure):
    def __init__(self, message: str, *, code: str = "provider_degraded") -> None:
        super().__init__(message, code=code, category="degraded")


class SignProviderAuthError(SignProviderFailure):
    def __init__(self, message: str, *, code: str = "provider_auth_error") -> None:
        super().__init__(message, code=code, category="auth_error")


class SignProviderRateLimitError(SignProviderFailure):
    def __init__(self, message: str, *, code: str = "provider_rate_limited") -> None:
        super().__init__(message, code=code, category="rate_limited")


class SignProviderTimeoutError(SignProviderFailure):
    def __init__(self, message: str, *, code: str = "provider_timeout") -> None:
        super().__init__(message, code=code, category="timeout")


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


__all__ = [
    "CertificateInfo",
    "SignProvider",
    "SignProviderAuthError",
    "SignProviderDegradedError",
    "SignProviderFailure",
    "SignProviderRateLimitError",
    "SignProviderTimeoutError",
    "SignedResult",
    "VerifyResult",
]
