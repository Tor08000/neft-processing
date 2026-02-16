from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

from fastapi import HTTPException

from app.domains.client.onboarding.documents.models import DocType
from app.domains.client.onboarding.models import ClientOnboardingApplication, OnboardingApplicationStatus

_ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png"}
_ALLOWED_UPLOAD_STATUSES = {OnboardingApplicationStatus.DRAFT.value, OnboardingApplicationStatus.SUBMITTED.value}
_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass(slots=True)
class PreparedUpload:
    filename: str
    mime: str
    size: int
    sha256: str


def max_upload_bytes() -> int:
    mb = int(os.getenv("MAX_UPLOAD_MB", "20"))
    return mb * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    sanitized = _SANITIZE_RE.sub("_", filename.strip())
    return sanitized or "document"


def parse_doc_type(value: str) -> DocType:
    try:
        return DocType(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"reason_code": "invalid_doc_type"}) from exc


def ensure_upload_allowed(application: ClientOnboardingApplication) -> None:
    if application.status not in _ALLOWED_UPLOAD_STATUSES:
        raise HTTPException(status_code=409, detail={"reason_code": "application_not_editable"})


def prepare_upload(filename: str, mime: str, data: bytes) -> PreparedUpload:
    if len(data) > max_upload_bytes():
        raise HTTPException(status_code=413, detail={"reason_code": "file_too_large"})
    if mime not in _ALLOWED_MIME:
        raise HTTPException(status_code=415, detail={"reason_code": "unsupported_mime"})
    return PreparedUpload(
        filename=sanitize_filename(filename),
        mime=mime,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
