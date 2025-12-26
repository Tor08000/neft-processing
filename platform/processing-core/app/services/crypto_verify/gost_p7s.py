from __future__ import annotations

from neft_shared.settings import get_settings

from app.services.crypto_verify.base import CertificateInfo, VerificationResult

settings = get_settings()


def verify_p7s_signature(payload: bytes, *, document_hash: str) -> VerificationResult:
    if not settings.LEGAL_GOST_VERIFY_ENABLED:
        return VerificationResult(
            verified=False,
            details={"reason": "crypto_verification_disabled"},
        )
    return VerificationResult(
        verified=False,
        details={"reason": "not_implemented"},
        certificate=CertificateInfo(
            subject_dn=None,
            issuer_dn=None,
            serial_number=None,
            thumbprint_sha256=None,
            valid_from=None,
            valid_to=None,
        ),
    )


__all__ = ["verify_p7s_signature"]
