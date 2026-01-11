from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from sqlalchemy.orm import Session

from app.models.bi import BiSyncRun, BiSyncRunStatus, BiSyncRunType, BiWatermark
from app.services.audit_service import AuditService, RequestContext
from app.services.bi.clickhouse import ClickhouseSyncError, sync_clickhouse
from app.services.bi.metrics import metrics as bi_metrics

logger = get_logger(__name__)
settings = get_settings()


class BiSyncError(Exception):
    """BI sync runtime error."""


def _upsert_watermark(db: Session, name: str, ts: datetime) -> None:
    watermark = db.query(BiWatermark).filter(BiWatermark.name == name).one_or_none()
    if not watermark:
        watermark = BiWatermark(name=name)
        db.add(watermark)
    watermark.last_updated_at = ts
    db.flush()


def run_sync(
    db: Session,
    *,
    run_type: BiSyncRunType,
    request_ctx: RequestContext | None = None,
) -> BiSyncRun:
    if not settings.BI_CLICKHOUSE_ENABLED:
        raise BiSyncError("bi_disabled")

    started_at = datetime.now(timezone.utc)
    run = BiSyncRun(type=run_type, status=BiSyncRunStatus.RUNNING, started_at=started_at)
    db.add(run)
    db.commit()
    db.refresh(run)

    audit_service = AuditService(db)
    try:
        timer = perf_counter()
        result = sync_clickhouse(db)
        duration = perf_counter() - timer
        rows_written = int(result.get("synced", 0))
        finished_at = datetime.now(timezone.utc)

        run.status = BiSyncRunStatus.COMPLETED
        run.rows_written = rows_written
        run.finished_at = finished_at
        db.commit()
        db.refresh(run)

        _upsert_watermark(db, "clickhouse_sync", finished_at)
        db.commit()

        bi_metrics.mark_sync_duration(duration)
        bi_metrics.mark_rows_written(rows_written)

        audit_service.audit(
            event_type="BI_SYNC_COMPLETED",
            entity_type="bi_sync_run",
            entity_id=run.id,
            action=run_type.value,
            request_ctx=request_ctx,
        )

        logger.info(
            "bi.sync_completed",
            extra={
                "type": run_type.value,
                "rows_written": rows_written,
                "duration_seconds": duration,
                "run_id": run.id,
            },
        )
        return run
    except ClickhouseSyncError as exc:
        run.status = BiSyncRunStatus.FAILED
        run.error = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        logger.exception("bi.sync_failed", extra={"run_id": run.id, "type": run_type.value})
        raise BiSyncError("sync_failed") from exc


__all__ = ["BiSyncError", "run_sync"]
