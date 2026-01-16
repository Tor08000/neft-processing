from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.export_jobs import ExportJob, ExportJobFormat, ExportJobStatus
from app.services.reports_render import (
    ExportRenderError,
    ExportRenderLimitError,
    ExportRenderValidationError,
    render_csv_payload,
    render_export_report,
    render_xlsx_payload,
)
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


@celery_client.task(name="exports.generate_export_job")
def generate_export_job(job_id: str) -> dict:
    session = get_sessionmaker()()
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
        render_result = render_export_report(
            session,
            report_type=job.report_type,
            client_id=str(job.org_id),
            tenant_id=int(tenant_id) if tenant_id is not None else None,
            org_id=str(job.org_id),
            created_by_user_id=job.created_by_user_id,
            filters=filters,
            allowed_entity_types=set(allowed_entity_types) if allowed_entity_types else None,
        )
        if job.format == ExportJobFormat.XLSX:
            payload = render_xlsx_payload(render_result)
            filename = _build_xlsx_filename(job.report_type.value, str(job.id))
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            payload = render_csv_payload(render_result)
            filename = render_result.filename
            content_type = "text/csv"

        object_key = _build_object_key(str(job.org_id), str(job.id), filename)
        storage = S3Storage(bucket=settings.NEFT_EXPORTS_BUCKET)
        storage.put_bytes(object_key, payload, content_type=content_type)

        job.status = ExportJobStatus.DONE
        job.file_object_key = object_key
        job.file_name = filename
        job.content_type = content_type
        job.row_count = len(render_result.rows)
        job.finished_at = datetime.now(timezone.utc)
        job.expires_at = job.expires_at or (datetime.now(timezone.utc) + timedelta(days=7))
        session.add(job)
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
            session.commit()
        logger.warning("export_job.limit_exceeded", extra={"job_id": job_id, "error": str(exc)})
        return {"status": "failed", "job_id": job_id, "error": str(exc)}
    except (ExportRenderValidationError, ExportRenderError) as exc:
        session.rollback()
        job = session.get(ExportJob, job_id)
        if job:
            job.status = ExportJobStatus.FAILED
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
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
            session.commit()
        logger.exception("export_job.error", extra={"job_id": job_id})
        raise
    finally:
        session.close()


__all__ = ["generate_export_job"]
