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


__all__ = ["EdoProviderAdapter", "ProviderStatus"]
