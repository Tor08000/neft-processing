from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.edo import EdoDocumentStatus


@dataclass(frozen=True)
class SbisStatusResult:
    status: EdoDocumentStatus
    provider_status: str
    provider_stage: str | None
    provider_substatus: str | None
    last_status_payload: dict[str, Any]


def map_sbis_status(payload: dict[str, Any]) -> SbisStatusResult:
    provider_status = str(payload.get("status") or payload.get("state") or "UNKNOWN").upper()
    provider_stage = payload.get("stage")
    provider_substatus = payload.get("substatus") or payload.get("sub_status")

    mapped = {
        "DRAFT": EdoDocumentStatus.DRAFT,
        "QUEUED": EdoDocumentStatus.QUEUED,
        "SENDING": EdoDocumentStatus.SENDING,
        "SENT": EdoDocumentStatus.SENT,
        "DELIVERED": EdoDocumentStatus.DELIVERED,
        "SIGNED": EdoDocumentStatus.SIGNED,
        "REJECTED": EdoDocumentStatus.REJECTED,
        "REVOKED": EdoDocumentStatus.REVOKED,
        "FAILED": EdoDocumentStatus.FAILED,
    }.get(provider_status, EdoDocumentStatus.UNKNOWN)

    return SbisStatusResult(
        status=mapped,
        provider_status=provider_status,
        provider_stage=provider_stage,
        provider_substatus=provider_substatus,
        last_status_payload=payload,
    )


__all__ = ["SbisStatusResult", "map_sbis_status"]
