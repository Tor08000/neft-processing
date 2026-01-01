from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from neft_shared.settings import get_settings

from app.models.audit_retention import AuditPurgeLog
from app.models.cases import CaseSnapshot
from app.services.audit_retention_service import has_active_legal_hold


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
    """Purge case snapshot exports (case_snapshots)."""

    settings = get_settings()
    effective_retention = retention_days or settings.AUDIT_EXPORT_RETENTION_DAYS
    resolved_now = _resolve_now(now)
    cutoff = resolved_now - timedelta(days=effective_retention)

    snapshots = (
        db.query(CaseSnapshot)
        .filter(CaseSnapshot.created_at < cutoff)
        .order_by(CaseSnapshot.created_at.asc())
        .all()
    )

    eligible: list[CaseSnapshot] = []
    skipped_hold = 0
    for snapshot in snapshots:
        if has_active_legal_hold(db, case_id=str(snapshot.case_id)):
            skipped_hold += 1
            continue
        eligible.append(snapshot)

    sample_ids = [str(snapshot.id) for snapshot in eligible[:sample_limit]]
    if dry_run:
        return PurgeResult(
            entity_type="case_snapshot",
            retention_days=effective_retention,
            candidates=len(eligible),
            purged=0,
            skipped_hold=skipped_hold,
            sample_ids=sample_ids,
        )

    purged = 0
    for snapshot in eligible:
        db.delete(snapshot)
        db.add(
            AuditPurgeLog(
                entity_type="case_snapshot",
                entity_id=str(snapshot.id),
                case_id=str(snapshot.case_id),
                policy=policy,
                retention_days=effective_retention,
                purged_by=purged_by,
            )
        )
        purged += 1

    return PurgeResult(
        entity_type="case_snapshot",
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
