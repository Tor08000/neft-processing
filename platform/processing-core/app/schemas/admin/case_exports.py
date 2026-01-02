from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.case_exports import CaseExportKind


class CaseExportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CaseExportKind
    case_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    mastery_snapshot: dict[str, Any] | None = None


class CaseExportDownload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    expires_in: int


class CaseExportOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: CaseExportKind
    case_id: str | None = None
    content_type: str
    content_sha256: str
    artifact_signature: str | None = None
    artifact_signature_alg: str | None = None
    artifact_signing_key_id: str | None = None
    artifact_signed_at: datetime | None = None
    size_bytes: int
    created_at: datetime
    deleted_at: datetime | None = None
    delete_reason: str | None = None
    download: CaseExportDownload | None = None


class CaseExportDownloadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    expires_in: int
    content_sha256: str


class CaseExportVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_hash_verified: bool
    artifact_signature_verified: bool
    signed_by: str | None = None
    signed_at: datetime | None = None
    audit_chain_verified: bool


class CaseExportListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CaseExportOut]


class CaseExportKindResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Literal["EXPLAIN", "DIFF", "CASE"]]


__all__ = [
    "CaseExportCreateRequest",
    "CaseExportDownload",
    "CaseExportDownloadResponse",
    "CaseExportListResponse",
    "CaseExportOut",
    "CaseExportVerifyResponse",
]
