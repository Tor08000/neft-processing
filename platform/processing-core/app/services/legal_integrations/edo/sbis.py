from __future__ import annotations

from app.services.legal_integrations.base import EnvelopeRef, EnvelopeStatus, SignedArtifact, SigningPayload
from app.services.legal_integrations.errors import ProviderNotConfigured


class SbisAdapter:
    provider = "sbis"

    def send_for_signing(self, document_id: str, payload: SigningPayload) -> EnvelopeRef:
        raise ProviderNotConfigured("adapter_not_wired:sbis")

    def get_status(self, envelope_id: str) -> EnvelopeStatus:
        raise ProviderNotConfigured("adapter_not_wired:sbis")

    def fetch_signed_artifacts(self, envelope_id: str) -> list[SignedArtifact]:
        raise ProviderNotConfigured("adapter_not_wired:sbis")


__all__ = ["SbisAdapter"]
