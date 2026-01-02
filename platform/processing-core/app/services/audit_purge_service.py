from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from neft_shared.settings import get_settings

from app.models.audit_retention import AuditPurgeLog
from app.models.case_exports import CaseExport
from app.services.audit_retention_service import has_active_legal_hold
from app.services.export_storage import ExportStorage


@dataclass
class PurgeResult:
    entity_type: str
    retention_days: int
    candidates: int
    purged: int
    skipped_hold: int
    sample_ids: list[str] = field(default_factory=list)


def _resolve_now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def purge_expired_exports(
    db: Session,
    now: datetime | None = None,
    *,
    retention_days: int | None = None,
    dry_run: bool = False,
    purged_by: str = "audit_purge_job",
    policy: str = "case_exports_retention",
    sample_limit: int = 10,
) -> PurgeResult:
    """Purge case exports (case_exports)."""

    settings = get_settings()
    effective_retention = retention_days or settings.AUDIT_EXPORT_RETENTION_DAYS
    resolved_now = _resolve_now(now)
    exports = (
        db.query(CaseExport)
        .filter(
            CaseExport.deleted_at.is_(None),
            CaseExport.retention_until.isnot(None),
            CaseExport.retention_until < resolved_now,
        )
        .order_by(CaseExport.retention_until.asc())
        .all()
    )
    if settings.S3_OBJECT_LOCK_ENABLED:
        exports = [
            export
            for export in exports
            if export.locked_until is not None and export.locked_until < resolved_now
        ]

    eligible: list[CaseExport] = []
    skipped_hold = 0
    for export in exports:
        if has_active_legal_hold(db, case_id=str(export.case_id) if export.case_id else None):
            skipped_hold += 1
            continue
        eligible.append(export)

    sample_ids = [str(export.id) for export in eligible[:sample_limit]]
    if dry_run:
        return PurgeResult(
            entity_type="case_export",
            retention_days=effective_retention,
            candidates=len(eligible),
            purged=0,
            skipped_hold=skipped_hold,
            sample_ids=sample_ids,
        )

    storage = ExportStorage()
    purged = 0
    for export in eligible:
        try:
            storage.delete(export.object_key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code == "AccessDenied" and settings.S3_OBJECT_LOCK_ENABLED:
                head = storage.head(export.object_key) or {}
                retain_until = head.get("ObjectLockRetainUntilDate")
                if retain_until:
                    export.locked_until = retain_until
                    db.add(export)
                continue
            raise
        export.deleted_at = resolved_now
        export.delete_reason = "retention"
        db.add(export)
        db.add(
            AuditPurgeLog(
                entity_type="case_export",
                entity_id=str(export.id),
                case_id=str(export.case_id) if export.case_id else None,
                policy=policy,
                retention_days=effective_retention,
                purged_by=purged_by,
                reason="retention",
            )
        )
        purged += 1

    return PurgeResult(
        entity_type="case_export",
        retention_days=effective_retention,
        candidates=len(eligible),
        purged=purged,
        skipped_hold=skipped_hold,
        sample_ids=sample_ids,
    )


def purge_expired_attachments(
    db: Session,
    now: datetime | None = None,
    *,
    retention_days: int | None = None,
    dry_run: bool = False,
    purged_by: str = "audit_purge_job",
    policy: str = "case_attachments_retention",
    sample_limit: int = 10,
) -> PurgeResult:
    settings = get_settings()
    effective_retention = retention_days or settings.AUDIT_ATTACHMENT_RETENTION_DAYS
    _ = (_resolve_now(now), sample_limit, purged_by, policy)
    if dry_run:
        return PurgeResult(
            entity_type="case_attachment",
            retention_days=effective_retention,
            candidates=0,
            purged=0,
            skipped_hold=0,
            sample_ids=[],
        )
    return PurgeResult(
        entity_type="case_attachment",
        retention_days=effective_retention,
        candidates=0,
        purged=0,
        skipped_hold=0,
        sample_ids=[],
    )


def purge_ephemeral(
    db: Session,
    now: datetime | None = None,
    *,
    retention_days: int | None = None,
    dry_run: bool = False,
    purged_by: str = "audit_purge_job",
    policy: str = "audit_ephemeral_retention",
    sample_limit: int = 10,
) -> PurgeResult:
    settings = get_settings()
    effective_retention = retention_days or settings.AUDIT_CACHE_RETENTION_DAYS
    _ = (_resolve_now(now), sample_limit, purged_by, policy, db)
    if dry_run:
        return PurgeResult(
            entity_type="ephemeral",
            retention_days=effective_retention,
            candidates=0,
            purged=0,
            skipped_hold=0,
            sample_ids=[],
        )
    return PurgeResult(
        entity_type="ephemeral",
        retention_days=effective_retention,
        candidates=0,
        purged=0,
        skipped_hold=0,
        sample_ids=[],
    )


__all__ = [
    "PurgeResult",
    "purge_expired_exports",
    "purge_expired_attachments",
    "purge_ephemeral",
]
