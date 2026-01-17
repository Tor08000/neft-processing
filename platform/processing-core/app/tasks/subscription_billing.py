from __future__ import annotations

from datetime import datetime, timezone

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.subscription_billing import (
    generate_invoice_pdf,
    generate_invoices_for_period,
    mark_invoice_overdue,
)
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@celery_client.task(
    name="billing.generate_subscription_invoices",
    bind=True,
    queue="billing",
    max_retries=2,
    default_retry_delay=30,
)
def generate_subscription_invoices(
    self,
    target_date: str | None = None,
    org_id: int | None = None,
    subscription_id: int | None = None,
) -> dict:
    session = get_sessionmaker()()
    try:
        if target_date:
            resolved_date = datetime.fromisoformat(target_date).date()
        else:
            resolved_date = datetime.now(timezone.utc).date()
        invoice_ids = generate_invoices_for_period(
            session,
            target_date=resolved_date,
            org_id=org_id,
            subscription_id=subscription_id,
            request_ctx=None,
        )
        for invoice_id in invoice_ids:
            try:
                generate_invoice_pdf(session, invoice_id=invoice_id)
            except Exception as exc:  # noqa: BLE001 - PDF should not block issuance
                logger.warning(
                    "subscription_invoice.pdf_failed",
                    extra={"invoice_id": invoice_id, "error": str(exc)},
                )
        session.commit()
        return {"created": len(invoice_ids), "invoice_ids": invoice_ids}
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.exception("subscription_invoice.generate_failed", extra={"error": str(exc)})
        raise
    finally:
        session.close()


@celery_client.task(
    name="billing.overdue_check",
    bind=True,
    queue="billing",
    max_retries=2,
    default_retry_delay=30,
)
def billing_overdue_check(self) -> dict:
    session = get_sessionmaker()()
    try:
        invoice_ids = mark_invoice_overdue(session)
        session.commit()
        return {"overdue": len(invoice_ids), "invoice_ids": invoice_ids}
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.exception("subscription_invoice.overdue_failed", extra={"error": str(exc)})
        raise
    finally:
        session.close()


__all__ = ["generate_subscription_invoices", "billing_overdue_check"]
