from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.export_jobs import ExportJob, ExportJobStatus
from app.models.report_schedules import ReportSchedule, ReportScheduleStatus
from app.services.audit_service import AuditService
from app.services.report_schedule_notifications import send_scheduled_report_notifications
from app.services.report_schedules import compute_next_run_at
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


def _trigger_schedule(session, schedule: ReportSchedule, now: datetime) -> None:
    if schedule.last_run_at and (now - schedule.last_run_at).total_seconds() < 60:
        return
    filters = dict(schedule.filters_json or {})
    filters["schedule_id"] = str(schedule.id)
    job = ExportJob(
        org_id=str(schedule.org_id),
        created_by_user_id=str(schedule.created_by_user_id),
        report_type=schedule.report_type,
        format=schedule.format,
        filters_json=filters,
        status=ExportJobStatus.QUEUED,
        expires_at=now + timedelta(days=7),
    )
    session.add(job)
    session.flush()

    schedule.last_run_at = now
    schedule.next_run_at = compute_next_run_at(schedule.schedule_kind, schedule.schedule_meta, schedule.timezone)
    session.add(schedule)

    try:
        celery_client.send_task("exports.generate_export_job", args=[str(job.id)])
    except Exception as exc:  # noqa: BLE001
        job.status = ExportJobStatus.FAILED
        job.error_message = "celery_not_available"
        session.add(job)
        send_scheduled_report_notifications(session, schedule=schedule, job=job, success=False)
        logger.warning("report_schedule.celery_not_available", extra={"schedule_id": str(schedule.id), "error": str(exc)})

    AuditService(session).audit(
        event_type="report_schedule_triggered",
        entity_type="report_schedule",
        entity_id=str(schedule.id),
        action="report_schedule_triggered",
        after={"export_job_id": str(job.id)},
    )


@celery_client.task(name="reports.run_report_schedules")
def run_report_schedules() -> dict:
    session = get_sessionmaker()()
    now = datetime.now(timezone.utc)
    triggered = 0
    try:
        schedules = (
            session.query(ReportSchedule)
            .filter(ReportSchedule.status == ReportScheduleStatus.ACTIVE)
            .filter(ReportSchedule.next_run_at.isnot(None))
            .filter(ReportSchedule.next_run_at <= now)
            .order_by(ReportSchedule.next_run_at.asc())
            .all()
        )
        for schedule in schedules:
            _trigger_schedule(session, schedule, now)
            session.commit()
            triggered += 1
        return {"status": "ok", "triggered": triggered}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("report_schedule_runner_failed")
        raise
    finally:
        session.close()


__all__ = ["run_report_schedules"]
