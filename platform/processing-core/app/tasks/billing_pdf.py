from __future__ import annotations

from uuid import uuid4
from datetime import date

from celery import Task

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.models.billing_job_run import BillingJobType
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


@celery_client.task(name="billing.run_monthly_invoices", bind=True)
def run_monthly_invoices_task(self: Task, month: str | None = None) -> dict:
    correlation_id = _make_correlation_id()
    session = get_sessionmaker()()
    job_service = BillingJobRunService(session)
    job_run = job_service.start(
        BillingJobType.INVOICE_MONTHLY,
        params={"month": month} if month else None,
        correlation_id=correlation_id,
        celery_task_id=self.request.id,
    )
    try:
        invoices = run_invoice_monthly(
            target_month=None if month is None else date.fromisoformat(f"{month}-01"),
            session=session,
        )

        link_service = BillingTaskLinkService(session)
        for invoice in invoices:
            link_service.upsert(
                invoice_id=invoice.id,
                task_type=BillingTaskType.MONTHLY_RUN,
                task_id=self.request.id,
                status=BillingTaskStatus.SUCCESS,
            )
            if invoice.pdf_status in {InvoicePdfStatus.NONE, InvoicePdfStatus.FAILED}:
                generate_invoice_pdf.delay(invoice.id, correlation_id=correlation_id)

        session.commit()
        job_service.succeed(
            job_run,
            metrics={"created": len(invoices)},
            result_ref={"invoices": [invoice.id for invoice in invoices]},
        )
        session.commit()
        return {"job_run_id": job_run.id, "invoices": [invoice.id for invoice in invoices]}
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        job_service.fail(job_run, error=str(exc))
        session.commit()
        raise
    finally:
        session.close()


@celery_client.task(name="billing.generate_invoice_pdf", bind=True, max_retries=5, default_retry_delay=15)
def generate_invoice_pdf(self: Task, invoice_id: str, *, correlation_id: str | None = None, force: bool = False) -> dict:
    session = get_sessionmaker()()
    link_service = BillingTaskLinkService(session)
    link_service.upsert(
        invoice_id=invoice_id,
        task_type=BillingTaskType.PDF_GENERATE,
        task_id=self.request.id,
        status=BillingTaskStatus.RUNNING,
    )
    session.commit()

    try:
        from app.models.invoice import Invoice

        invoice = session.query(Invoice).filter_by(id=invoice_id).one()
        pdf_service = InvoicePdfService(session)
        pdf_service.generate(invoice, force=force)
        session.commit()

        link_service.upsert(
            invoice_id=invoice_id,
            task_type=BillingTaskType.PDF_GENERATE,
            task_id=self.request.id,
            status=BillingTaskStatus.SUCCESS,
        )
        session.commit()
        return {"invoice_id": invoice_id, "pdf_status": invoice.pdf_status}
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        link_service.upsert(
            invoice_id=invoice_id,
            task_type=BillingTaskType.PDF_GENERATE,
            task_id=self.request.id,
            status=BillingTaskStatus.FAILED,
            error=str(exc),
        )
        session.commit()
        raise self.retry(exc=exc)
    finally:
        session.close()
