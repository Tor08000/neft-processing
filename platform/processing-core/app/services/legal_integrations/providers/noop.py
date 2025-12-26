from __future__ import annotations

from datetime import datetime, timezone

from app.models.documents import DocumentFileType
from app.models.legal_integrations import DocumentEnvelopeStatus, SignatureType
from app.services.legal_integrations.base import EnvelopeRef, EnvelopeStatus, SignedArtifact, SigningPayload


class NoopLegalAdapter:
    provider = "noop"

    def send_for_signing(self, document_id: str, payload: SigningPayload) -> EnvelopeRef:
        return EnvelopeRef(provider=self.provider, envelope_id=f"noop-{document_id}", status=DocumentEnvelopeStatus.SENT)

    def get_status(self, envelope_id: str) -> EnvelopeStatus:
        return EnvelopeStatus(
            provider=self.provider,
            envelope_id=envelope_id,
            status=DocumentEnvelopeStatus.SIGNED,
            status_at=datetime.now(timezone.utc),
        )

    def fetch_signed_artifacts(self, envelope_id: str) -> list[SignedArtifact]:
        return [
            SignedArtifact(
                file_type=DocumentFileType.SIG,
                signature_type=SignatureType.ESIGN,
                payload=b"noop-signature",
                content_type="application/octet-stream",
                signed_at=datetime.now(timezone.utc),
                meta={"source": "noop"},
            )
        ]


__all__ = ["NoopLegalAdapter"]
