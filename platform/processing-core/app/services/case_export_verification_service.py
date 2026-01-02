from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.case_exports import CaseExport
from app.services.audit_signing import AuditSigningService
from app.services.case_events_service import verify_case_event_chain, verify_case_event_signatures
from app.services.export_storage import ExportStorage


@dataclass(frozen=True)
class ExportVerificationResult:
    content_hash_verified: bool
    artifact_signature_verified: bool
    signed_by: str | None
    signed_at: datetime | None
    audit_chain_verified: bool


def verify_export(db: Session, *, export: CaseExport) -> ExportVerificationResult:
    storage = ExportStorage()
    content_hash_verified = False
    artifact_signature_verified = False
    signed_by = export.artifact_signing_key_id
    signed_at = export.artifact_signed_at

    try:
        payload_bytes = storage.get_bytes(export.object_key)
    except Exception:  # noqa: BLE001
        payload_bytes = b""
    if payload_bytes:
        computed_hash = hashlib.sha256(payload_bytes).hexdigest()
        content_hash_verified = computed_hash == export.content_sha256

    if export.artifact_signature and export.artifact_signature_alg and export.artifact_signing_key_id:
        signing_service = AuditSigningService()
        try:
            message = bytes.fromhex(export.content_sha256)
        except ValueError:
            message = b""
        if message:
            artifact_signature_verified = signing_service.verify(
                message=message,
                signature_b64=export.artifact_signature,
                alg=export.artifact_signature_alg,
                key_id=export.artifact_signing_key_id,
            )

    audit_chain_verified = False
    if export.case_id:
        chain_result = verify_case_event_chain(db, case_id=str(export.case_id))
        signature_result = verify_case_event_signatures(db, case_id=str(export.case_id))
        audit_chain_verified = chain_result.verified and signature_result.verified

    return ExportVerificationResult(
        content_hash_verified=content_hash_verified,
        artifact_signature_verified=artifact_signature_verified,
        signed_by=signed_by,
        signed_at=signed_at,
        audit_chain_verified=audit_chain_verified,
    )


__all__ = ["ExportVerificationResult", "verify_export"]
