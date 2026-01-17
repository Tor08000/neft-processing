from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.export_jobs import ExportJob, ExportJobFormat, ExportJobStatus
from app.models.report_schedules import ReportSchedule
from app.services.reports_render import (
    ExportRenderError,
    ExportRenderLimitError,
    ExportRenderValidationError,
    TOO_MANY_ROWS_ERROR,
    render_export_report_stream,
    write_csv_stream,
    write_xlsx_stream,
)
from app.services.report_schedule_notifications import send_scheduled_report_notifications
from app.services.audit_service import AuditService
from app.services.s3_storage import S3Storage
from app.services.client_notifications import ClientNotificationSeverity, create_notification
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


def _build_object_key(org_id: str, job_id: str, filename: str) -> str:
    return f"{org_id}/{job_id}/{filename}"


def _build_xlsx_filename(report_type: str, job_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return f"{report_type}_{stamp}_{job_id}.xlsx"


def _notify_schedule_if_needed(session, job: ExportJob, success: bool) -> None:
    schedule_id = None
    if isinstance(job.filters_json, dict):
        schedule_id = job.filters_json.get("schedule_id")
    if schedule_id:
        schedule = session.get(ReportSchedule, schedule_id)
        if schedule:
            send_scheduled_report_notifications(session, schedule=schedule, job=job, success=success)


def _failure_notification_body(error_message: str | None) -> str:
    if error_message == TOO_MANY_ROWS_ERROR:
        return "Слишком большой объём данных — сузьте фильтры."
    if error_message == "timeout":
        return "Превышено время формирования отчёта. Попробуйте сузить фильтры."
    return "Не удалось сформировать отчёт."


def _notify_export_failure(session, job: ExportJob) -> None:
    try:
        create_notification(
            session,
            org_id=str(job.org_id),
            event_type="export_failed",
            severity=ClientNotificationSeverity.WARNING,
            title=f"Ошибка экспорта {job.format.value}",
            body=_failure_notification_body(job.error_message),
            link="/client/exports",
            target_user_id=job.created_by_user_id,
            entity_type="report_export",
            entity_id=str(job.id),
            meta_json={"row_count": job.row_count, "format": job.format.value},
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.warning("export_job.failure_notification_failed", extra={"job_id": str(job.id), "error": str(exc)})


@celery_client.task(
    name="exports.generate_export_job",
    soft_time_limit=settings.NEFT_EXPORT_JOB_SOFT_TIME_LIMIT_SECONDS,
)
def generate_export_job(job_id: str) -> dict:
    session = get_sessionmaker()()
    temp_path: Path | None = None
    try:
        job = session.get(ExportJob, job_id)
        if not job:
            return {"status": "not_found", "job_id": job_id}
        if job.status in {ExportJobStatus.DONE, ExportJobStatus.CANCELED, ExportJobStatus.EXPIRED}:
            return {"status": "skipped", "job_id": job_id}

        job.status = ExportJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        session.add(job)
        session.commit()

        filters = job.filters_json or {}
        tenant_id = filters.get("tenant_id")
        allowed_entity_types = filters.get("allowed_entity_types")
        render_result = render_export_report_stream(
            session,
            report_type=job.report_type,
            client_id=str(job.org_id),
            tenant_id=int(tenant_id) if tenant_id is not None else None,
            org_id=str(job.org_id),
            created_by_user_id=job.created_by_user_id,
            filters=filters,
            allowed_entity_types=set(allowed_entity_types) if allowed_entity_types else None,
            max_rows=settings.NEFT_EXPORT_MAX_ROWS,
            chunk_size=settings.NEFT_EXPORT_CHUNK_SIZE,
        )
        temp_dir = Path(settings.NEFT_EXPORT_TMP_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_suffix = "xlsx" if job.format == ExportJobFormat.XLSX else "csv"
        temp_path = temp_dir / f"export_{job.id}_{uuid4().hex}.{temp_suffix}"
        if job.format == ExportJobFormat.XLSX:
            filename = _build_xlsx_filename(job.report_type.value, str(job.id))
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            row_count = write_xlsx_stream(
                render_result,
                file_path=str(temp_path),
                max_rows=settings.NEFT_EXPORT_MAX_ROWS,
            )
        else:
            filename = render_result.filename
            content_type = "text/csv"
            row_count = write_csv_stream(
                render_result,
                file_path=str(temp_path),
                max_rows=settings.NEFT_EXPORT_MAX_ROWS,
            )

        object_key = _build_object_key(str(job.org_id), str(job.id), filename)
        storage = S3Storage(bucket=settings.NEFT_EXPORTS_BUCKET)
        storage.put_file(object_key, str(temp_path), content_type=content_type)

        job.status = ExportJobStatus.DONE
        job.file_object_key = object_key
        job.file_name = filename
        job.content_type = content_type
        job.row_count = row_count
        job.finished_at = datetime.now(timezone.utc)
        job.expires_at = job.expires_at or (
            datetime.now(timezone.utc) + timedelta(days=settings.EXPORT_JOB_RETENTION_DAYS)
        )
        session.add(job)
        _notify_schedule_if_needed(session, job, True)
        session.commit()

        try:
            create_notification(
                session,
                org_id=str(job.org_id),
                event_type="export_ready",
                severity=ClientNotificationSeverity.INFO,
                title=f"Отчёт {job.format.value} готов",
                body=f"Выгрузка {job.format.value} готова к скачиванию.",
                link="/client/exports",
                target_user_id=job.created_by_user_id,
                entity_type="report_export",
                entity_id=str(job.id),
                meta_json={"row_count": job.row_count, "format": job.format.value},
            )
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.warning("export_job.notification_failed", extra={"job_id": job_id, "error": str(exc)})

        return {"status": "done", "job_id": job_id}
    except ExportRenderLimitError as exc:
        session.rollback()
        job = session.get(ExportJob, job_id)
        if job:
            job.status = ExportJobStatus.FAILED
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            session.add(job)
            _notify_schedule_if_needed(session, job, False)
            session.commit()
            _notify_export_failure(session, job)
        logger.warning("export_job.limit_exceeded", extra={"job_id": job_id, "error": str(exc)})
        return {"status": "failed", "job_id": job_id, "error": str(exc)}
    except SoftTimeLimitExceeded:
        session.rollback()
        job = session.get(ExportJob, job_id)
        if job:
            job.status = ExportJobStatus.FAILED
            job.error_message = "timeout"
            job.finished_at = datetime.now(timezone.utc)
            session.add(job)
            _notify_schedule_if_needed(session, job, False)
            session.commit()
            _notify_export_failure(session, job)
        logger.warning("export_job.timeout", extra={"job_id": job_id})
        return {"status": "failed", "job_id": job_id, "error": "timeout"}
    except (ExportRenderValidationError, ExportRenderError) as exc:
        session.rollback()
        job = session.get(ExportJob, job_id)
        if job:
            job.status = ExportJobStatus.FAILED
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            session.add(job)
            _notify_schedule_if_needed(session, job, False)
            session.commit()
            _notify_export_failure(session, job)
        logger.warning("export_job.failed", extra={"job_id": job_id, "error": str(exc)})
        return {"status": "failed", "job_id": job_id, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        job = session.get(ExportJob, job_id)
        if job:
            job.status = ExportJobStatus.FAILED
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            session.add(job)
            _notify_schedule_if_needed(session, job, False)
            session.commit()
            _notify_export_failure(session, job)
        logger.exception("export_job.error", extra={"job_id": job_id})
        raise
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                logger.warning("export_job.temp_cleanup_failed", extra={"job_id": job_id, "path": str(temp_path)})
        session.close()

@celery_client.task(name="exports.cleanup_expired_exports")
def cleanup_expired_exports(*, limit: int = 500) -> dict[str, int]:
    session = get_sessionmaker()()
    now = datetime.now(timezone.utc)
    expired = 0
    errors = 0
    try:
        jobs = (
            session.query(ExportJob)
            .filter(
                ExportJob.status == ExportJobStatus.DONE,
                ExportJob.expires_at.isnot(None),
                ExportJob.expires_at < now,
            )
            .order_by(ExportJob.expires_at.asc())
            .limit(limit)
            .all()
        )
        if not jobs:
            return {"expired": 0, "errors": 0}

        storage = S3Storage(bucket=settings.NEFT_EXPORTS_BUCKET)
        audit = AuditService(session)
        for job in jobs:
            try:
                if job.file_object_key:
                    storage.delete(job.file_object_key)
                job.status = ExportJobStatus.EXPIRED
                job.file_object_key = None
                job.content_type = None
                session.add(job)
                audit.audit(
                    event_type="export_expired",
                    entity_type="export_job",
                    entity_id=str(job.id),
                    action="export_expired",
                    after={
                        "report_type": job.report_type.value,
                        "format": job.format.value,
                        "expired_at": job.expires_at.isoformat() if job.expires_at else None,
                    },
                )
                session.commit()
                expired += 1
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                errors += 1
                logger.warning(
                    "export_job.cleanup_failed",
                    extra={"job_id": str(job.id), "error": str(exc)},
                )
        return {"expired": expired, "errors": errors}
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("export_job.cleanup_runner_failed")
        raise
    finally:
        session.close()


__all__ = ["cleanup_expired_exports", "generate_export_job"]
