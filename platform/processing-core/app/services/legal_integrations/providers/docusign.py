from __future__ import annotations

from app.services.legal_integrations.base import EnvelopeRef, EnvelopeStatus, SignedArtifact, SigningPayload


class DocuSignAdapter:
    provider = "docusign"

    def send_for_signing(self, document_id: str, payload: SigningPayload) -> EnvelopeRef:
        raise NotImplementedError("docusign adapter not implemented")

    def get_status(self, envelope_id: str) -> EnvelopeStatus:
        raise NotImplementedError("docusign adapter not implemented")

    def fetch_signed_artifacts(self, envelope_id: str) -> list[SignedArtifact]:
        raise NotImplementedError("docusign adapter not implemented")


__all__ = ["DocuSignAdapter"]
