from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderStatus:
    status: str
    provider_document_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class EdoProviderAdapter(Protocol):
    def send(self, document_bytes: bytes, meta: dict) -> str:
        ...

    def poll(self, provider_message_id: str) -> ProviderStatus:
        ...

    def download_signed(self, provider_message_id: str) -> bytes | None:
        ...


class ProviderFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        error_type: str = "provider_error",
        retryable: bool = False,
        provider: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.error_type = error_type
        self.retryable = retryable
        self.provider = provider


class ProviderTimeoutError(ProviderFailure):
    def __init__(self, message: str, *, code: str = "provider_timeout", provider: str | None = None) -> None:
        super().__init__(message, code=code, error_type="timeout", retryable=True, provider=provider)


class ProviderAuthError(ProviderFailure):
    def __init__(self, message: str, *, code: str = "provider_auth_error", provider: str | None = None) -> None:
        super().__init__(message, code=code, error_type="auth_error", retryable=False, provider=provider)


class ProviderDegradedError(ProviderFailure):
    def __init__(self, message: str, *, code: str = "provider_degraded", provider: str | None = None) -> None:
        super().__init__(message, code=code, error_type="degraded", retryable=False, provider=provider)


__all__ = [
    "EdoProviderAdapter",
    "ProviderAuthError",
    "ProviderDegradedError",
    "ProviderFailure",
    "ProviderStatus",
    "ProviderTimeoutError",
]
