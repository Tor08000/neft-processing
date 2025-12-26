from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CertificateInfo:
    subject_dn: str | None
    issuer_dn: str | None
    serial_number: str | None
    thumbprint_sha256: str | None
    valid_from: datetime | None
    valid_to: datetime | None


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    details: dict
    certificate: CertificateInfo | None = None


__all__ = ["CertificateInfo", "VerificationResult"]
