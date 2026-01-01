from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

from app.db.types import new_uuid_str
from app.models.case_exports import CaseExport, CaseExportKind
from app.models.cases import CaseEventType
from app.services.audit_retention_service import compute_export_retention_until
from app.services.case_event_hashing import canonical_json
from app.services.case_event_redaction import redact_deep
from app.services.case_events_service import CaseEventActor, CaseEventArtifact, emit_case_event
from app.services.export_storage import ExportStorage

logger = get_logger(__name__)
settings = get_settings()


EXPORT_ARTIFACT_KIND = {
    CaseExportKind.EXPLAIN: "explain_export",
    CaseExportKind.DIFF: "diff_export",
    CaseExportKind.CASE: "case_export",
}


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return prefix if prefix.endswith("/") else f"{prefix}/"


def _build_object_key(export_id: str, *, case_id: UUID | str | None, kind: CaseExportKind, now: datetime) -> str:
    prefix = _normalize_prefix(settings.S3_EXPORTS_PREFIX)
    case_segment = str(case_id) if case_id else "nocase"
    return f"{prefix}{case_segment}/{kind.value.lower()}/{now:%Y/%m}/{export_id}.json"


def _redact_export(payload: dict[str, Any]) -> dict[str, Any]:
    return redact_deep(payload, "", include_hash=True)


def _serialize_payload(payload: dict[str, Any]) -> bytes:
    return canonical_json(payload).encode("utf-8")


def create_export(
    db,
    *,
    kind: Literal["EXPLAIN", "DIFF", "CASE"],
    case_id: UUID | str | None,
    payload: dict[str, Any],
    actor: CaseEventActor | None,
    request_id: str | None,
    trace_id: str | None,
) -> CaseExport:
    export_kind = CaseExportKind(kind)
    export_id = new_uuid_str()
    now = datetime.now(timezone.utc)
    redacted_payload = _redact_export(payload)
    content_bytes = _serialize_payload(redacted_payload)
    content_sha256 = hashlib.sha256(content_bytes).hexdigest()
    object_key = _build_object_key(export_id, case_id=case_id, kind=export_kind, now=now)

    storage = ExportStorage()
    storage.put_bytes(object_key, content_bytes, content_type="application/json")

    try:
        retention_until = compute_export_retention_until(now=now)
        export = CaseExport(
            id=export_id,
            case_id=str(case_id) if case_id else None,
            kind=export_kind,
            object_key=object_key,
            content_type="application/json",
            content_sha256=content_sha256,
            size_bytes=len(content_bytes),
            created_at=now,
            created_by_user_id=actor.id if actor else None,
            request_id=request_id,
            trace_id=trace_id,
            retention_until=retention_until,
        )
        db.add(export)
        if case_id:
            emit_case_event(
                db,
                case_id=str(case_id),
                event_type=CaseEventType.EXPORT_CREATED,
                actor=actor,
                request_id=request_id,
                trace_id=trace_id,
                artifact=CaseEventArtifact(
                    kind=EXPORT_ARTIFACT_KIND[export_kind],
                    id=export_id,
                    url=None,
                ),
                extra_payload={"content_sha256": content_sha256},
            )
        return export
    except Exception:
        logger.exception("case_export_create_failed", extra={"export_id": export_id})
        try:
            storage.delete(object_key)
        except Exception:
            logger.exception("case_export_cleanup_failed", extra={"object_key": object_key})
        raise


__all__ = ["create_export"]
