from __future__ import annotations

from uuid import uuid4
from datetime import date

from celery import Task

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from app.models.billing_task_link import BillingTaskStatus, BillingTaskType
from app.models.invoice import InvoicePdfStatus
from app.services.billing_job_runs import BillingJobRunService
from app.services.billing_task_links import BillingTaskLinkService
from app.services.invoice_pdf import InvoicePdfService
from app.services.invoicing.monthly import run_invoice_monthly
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


def _make_correlation_id() -> str:
    return str(uuid4())


@celery_client.task(name="billing.generate_monthly_invoices", bind=True, queue="billing", max_retries=2, default_retry_delay=15)
def run_monthly_invoices_task(
    self: Task, month: str | None = None, job_run_id: str | None = None, correlation_id: str | None = None
) -> dict:
    session = get_sessionmaker()()
    job_run = session.get(BillingJobRun, job_run_id) if job_run_id else None
    correlation_id = correlation_id or (job_run.correlation_id if job_run else _make_correlation_id())
    link_service = BillingTaskLinkService(session)
    try:
        outcome = run_invoice_monthly(
            target_month=None if month is None else date.fromisoformat(f"{month}-01"),
            session=session,
            correlation_id=correlation_id,
            celery_task_id=self.request.id,
            job_run=job_run,
        )
        invoices = outcome.invoices

        for invoice in invoices:
            link_service.upsert(
                task_id=self.request.id,
                task_name="billing.generate_monthly_invoices",
                job_run_id=outcome.job_run.id,
                task_type=BillingTaskType.MONTHLY_RUN,
                invoice_id=invoice.id,
                status=BillingTaskStatus.SUCCESS,
                billing_period_id=str(invoice.billing_period_id) if invoice.billing_period_id else None,
            )
            if invoice.pdf_status in {InvoicePdfStatus.NONE, InvoicePdfStatus.FAILED}:
                invoice.pdf_status = InvoicePdfStatus.QUEUED
                invoice.pdf_error = None
                session.add(invoice)
                session.flush()
                generate_invoice_pdf.delay(invoice.id, correlation_id=correlation_id)

        session.commit()
        return {"job_run_id": str(outcome.job_run.id), "invoices": [invoice.id for invoice in invoices]}
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        if "outcome" in locals():
            link_service.upsert(
                task_id=self.request.id,
                task_name="billing.generate_monthly_invoices",
                job_run_id=outcome.job_run.id,
                task_type=BillingTaskType.MONTHLY_RUN,
                status=BillingTaskStatus.FAILED,
                error=str(exc),
            )
            session.commit()
        raise self.retry(exc=exc)
    finally:
        session.close()


@celery_client.task(name="billing.generate_invoice_pdf", bind=True, queue="pdf", max_retries=3, default_retry_delay=5)
def generate_invoice_pdf(
    self: Task,
    invoice_id: str,
    *,
    correlation_id: str | None = None,
    force: bool = False,
    job_run_id: str | None = None,
) -> dict:
    session = get_sessionmaker()()
    link_service = BillingTaskLinkService(session)
    try:
        from app.models.invoice import Invoice

        job_service = BillingJobRunService(session)
        job_run = session.get(BillingJobRun, job_run_id) if job_run_id else None
        if job_run is None:
            job_run = job_service.start(
                BillingJobType.PDF_GENERATE,
                params={"invoice_id": invoice_id, "force": force},
                correlation_id=correlation_id,
                celery_task_id=self.request.id,
                invoice_id=invoice_id,
            )
        else:
            job_run.status = BillingJobStatus.STARTED
            job_run.params = job_run.params or {"invoice_id": invoice_id, "force": force}
            job_run.celery_task_id = self.request.id
            job_run.correlation_id = correlation_id or job_run.correlation_id
            session.add(job_run)
            session.flush()

        link_service.upsert(
            task_id=self.request.id,
            task_name="billing.generate_invoice_pdf",
            job_run_id=job_run.id,
            task_type=BillingTaskType.PDF_GENERATE,
            invoice_id=invoice_id,
            status=BillingTaskStatus.RUNNING,
        )
        session.commit()

        invoice = session.query(Invoice).filter_by(id=invoice_id).one()
        pdf_service = InvoicePdfService(session)
        pdf_service.generate(invoice, force=force)
        session.commit()

        link_service.upsert(
            task_id=self.request.id,
            task_name="billing.generate_invoice_pdf",
            job_run_id=job_run.id,
            task_type=BillingTaskType.PDF_GENERATE,
            status=BillingTaskStatus.SUCCESS,
            invoice_id=invoice_id,
        )
        job_service.succeed(
            job_run,
            metrics={
                "invoice_id": invoice_id,
                "pdf_status": str(invoice.pdf_status),
                "pdf_version": invoice.pdf_version,
            },
        )
        session.commit()
        return {"invoice_id": invoice_id, "pdf_status": invoice.pdf_status}
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        if "job_run" in locals():
            link_service.upsert(
                task_id=self.request.id,
                task_name="billing.generate_invoice_pdf",
                job_run_id=job_run.id,
                task_type=BillingTaskType.PDF_GENERATE,
                status=BillingTaskStatus.FAILED,
                error=str(exc),
                invoice_id=invoice_id,
            )
            job_service.fail(job_run, error=str(exc))
            session.commit()
        retries = getattr(self.request, "retries", 0)
        delay = [5, 30, 120][retries] if retries < 3 else 120
        raise self.retry(exc=exc, countdown=delay)
    finally:
        session.close()
