from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.export_jobs import ExportJob, ExportJobStatus
from app.models.report_schedules import ReportSchedule, ReportScheduleStatus
from app.services.audit_service import AuditService
from app.services.billing_access import BillingActionKind, billing_policy_allow, get_subscription_status
from app.services.report_schedule_notifications import send_scheduled_report_notifications
from app.services.report_schedules import compute_next_run_at
from app.services.export_metrics import metrics as export_metrics
from app.services.report_schedule_metrics import metrics as schedule_metrics
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


SAFETY_WINDOW_SECONDS = 30


def _trigger_schedule(session, schedule: ReportSchedule, now: datetime) -> None:
    if schedule.last_run_at and (now - schedule.last_run_at).total_seconds() < 60:
        schedule_metrics.mark_skipped("not_due")
        return
    filters = dict(schedule.filters_json or {})
    filters["schedule_id"] = str(schedule.id)
    if schedule.next_run_at:
        schedule_metrics.observe_lag((now - schedule.next_run_at).total_seconds())
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
    export_metrics.mark_created(schedule.report_type.value, schedule.format.value)

    schedule.last_run_at = now
    schedule.next_run_at = compute_next_run_at(
        schedule.schedule_kind,
        schedule.schedule_meta,
        schedule.timezone,
        anchor_utc=now + timedelta(seconds=1),
    )
    session.add(schedule)

    try:
        celery_client.send_task("exports.generate_export_job", args=[str(job.id)])
    except Exception as exc:  # noqa: BLE001
        job.status = ExportJobStatus.FAILED
        job.error_message = "celery_not_available"
        session.add(job)
        send_scheduled_report_notifications(session, schedule=schedule, job=job, success=False)
        logger.warning(
            "report_schedule.celery_not_available",
            extra={"schedule_id": str(schedule.id), "export_job_id": str(job.id), "error": str(exc)},
        )
    else:
        schedule_metrics.mark_triggered(schedule.report_type.value, schedule.format.value)

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
    due_before = now - timedelta(seconds=SAFETY_WINDOW_SECONDS)
    triggered = 0
    try:
        schedules = (
            session.query(ReportSchedule)
            .filter(ReportSchedule.status == ReportScheduleStatus.ACTIVE)
            .filter(ReportSchedule.next_run_at.isnot(None))
            .filter(ReportSchedule.next_run_at <= due_before)
            .order_by(ReportSchedule.next_run_at.asc())
            .with_for_update(skip_locked=True)
            .all()
        )
        for schedule in schedules:
            org_id = None
            try:
                org_id = int(schedule.org_id)
            except (TypeError, ValueError):
                org_id = None
            if org_id is not None:
                subscription_status = get_subscription_status(session, org_id=org_id)
                if not billing_policy_allow(BillingActionKind.SCHEDULE_TRIGGER, subscription_status):
                    schedule_metrics.mark_skipped("billing_blocked")
                    AuditService(session).audit(
                        event_type="schedule_skipped_billing",
                        entity_type="report_schedule",
                        entity_id=str(schedule.id),
                        action="schedule_skipped_billing",
                        after={
                            "org_id": str(schedule.org_id),
                            "subscription_status": subscription_status,
                        },
                    )
                    session.commit()
                    continue
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
