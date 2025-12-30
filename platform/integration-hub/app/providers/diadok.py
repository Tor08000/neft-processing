from __future__ import annotations

import time
from dataclasses import dataclass

from app.providers.base import ProviderStatus


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


__all__ = ["MockDiadokProvider"]
