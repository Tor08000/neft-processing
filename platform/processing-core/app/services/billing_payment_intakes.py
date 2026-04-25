from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import MetaData, Table, insert, func, or_, select, update
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA
from app.models.audit_log import ActorType
from app.services.audit_service import RequestContext
from app.services.billing_service import capture_payment, reactivate_subscription_storage
from app.services.case_events_service import CaseEventActor
from app.services.subscription_billing import update_invoice_status


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _tables_ready(db: Session, table_names: list[str]) -> bool:
    try:
        from sqlalchemy import inspect

        inspector = inspect(db.get_bind())
        return all(inspector.has_table(name, schema=DB_SCHEMA) for name in table_names)
    except Exception:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _invoice_id_variants(invoice_id: str | int) -> list[str | int]:
    variants: list[str | int] = [invoice_id]
    if isinstance(invoice_id, int):
        variants.append(str(invoice_id))
        return variants
    normalized = str(invoice_id).strip()
    if normalized and normalized not in variants:
        variants.append(normalized)
    if normalized.isdigit():
        variants.append(int(normalized))
    return variants


def _invoice_id_filter(column, invoice_id: str | int):
    variants = _invoice_id_variants(invoice_id)
    if len(variants) == 1:
        return column == variants[0]
    return or_(*[column == variant for variant in variants])


def _is_billing_flow_invoice(invoice: dict[str, Any] | None) -> bool:
    if not invoice:
        return False
    return all(
        key in invoice
        for key in ("client_id", "invoice_number", "amount_total", "amount_paid", "idempotency_key", "ledger_tx_id", "audit_event_id")
    )


def billing_flow_invoice_amount_due(invoice: dict[str, Any] | None) -> Decimal | None:
    if not _is_billing_flow_invoice(invoice):
        return None
    total_amount = invoice.get("amount_total")
    if total_amount is None:
        return None
    amount_paid = invoice.get("amount_paid")
    return Decimal(str(total_amount)) - Decimal(str(amount_paid or 0))


def _request_ctx_to_case_actor(request_ctx: RequestContext | None) -> CaseEventActor | None:
    if request_ctx is None:
        return None
    if request_ctx.actor_id is None and request_ctx.actor_email is None:
        return None
    return CaseEventActor(id=request_ctx.actor_id, email=request_ctx.actor_email)


def list_payment_intakes(
    db: Session,
    *,
    org_id: int | None = None,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return [], 0
    intakes = _table(db, "billing_payment_intakes")
    query = select(intakes)
    if org_id is not None:
        query = query.where(intakes.c.org_id == org_id)
    if status:
        query = query.where(intakes.c.status == status)
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0
    rows = (
        db.execute(query.order_by(intakes.c.created_at.desc(), intakes.c.id.desc()).offset(offset).limit(limit))
        .mappings()
        .all()
    )
    return rows, total


def get_payment_intake(db: Session, *, intake_id: int) -> dict[str, Any] | None:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return None
    intakes = _table(db, "billing_payment_intakes")
    return (
        db.execute(select(intakes).where(intakes.c.id == intake_id))
        .mappings()
        .first()
    )


def get_invoice(db: Session, *, invoice_id: str | int) -> dict[str, Any] | None:
    if not _tables_ready(db, ["billing_invoices"]):
        return None
    invoices = _table(db, "billing_invoices")
    return (
        db.execute(select(invoices).where(_invoice_id_filter(invoices.c.id, invoice_id)))
        .mappings()
        .first()
    )


def list_invoice_payment_intakes(db: Session, *, invoice_id: str | int) -> list[dict[str, Any]]:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return []
    intakes = _table(db, "billing_payment_intakes")
    rows = (
        db.execute(
            select(intakes)
            .where(_invoice_id_filter(intakes.c.invoice_id, invoice_id))
            .order_by(intakes.c.created_at.desc(), intakes.c.id.desc())
        )
        .mappings()
        .all()
    )
    return rows


def create_payment_intake(
    db: Session,
    *,
    org_id: int,
    invoice_id: str | int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    intakes = _table(db, "billing_payment_intakes")
    insert_stmt = (
        insert(intakes)
        .values(**payload, org_id=org_id, invoice_id=invoice_id, created_at=_now())
        .returning(intakes)
    )
    return db.execute(insert_stmt).mappings().first()


def approve_invoice_payment_intake(
    db: Session,
    *,
    intake: dict[str, Any],
    request_ctx: RequestContext | None,
) -> dict[str, Any] | None:
    tenant_id = int(intake["org_id"])
    invoice = get_invoice(db, invoice_id=intake["invoice_id"])
    if not invoice:
        return None
    if _is_billing_flow_invoice(invoice):
        intake_amount = Decimal(str(intake["amount"]))
        amount_due = billing_flow_invoice_amount_due(invoice)
        if amount_due is not None:
            if amount_due <= 0:
                raise ValueError("invoice_already_paid")
            if intake_amount > amount_due:
                raise ValueError("payment_amount_exceeds_due")
        capture_payment(
            db,
            tenant_id=tenant_id,
            invoice_id=str(invoice["id"]),
            provider="MANUAL_PAYMENT_INTAKE",
            provider_payment_id=intake.get("bank_reference"),
            amount=intake_amount,
            currency=str(intake["currency"]),
            idempotency_key=f"payment-intake:{intake['id']}",
            actor=_request_ctx_to_case_actor(request_ctx) or CaseEventActor(id="billing-payment-intake"),
            request_id=request_ctx.request_id if request_ctx else None,
            trace_id=request_ctx.trace_id if request_ctx else None,
        )
        approved_invoice = get_invoice(db, invoice_id=str(invoice["id"]))
        if approved_invoice and str(approved_invoice.get("status") or "").upper() == "PAID":
            reactivate_subscription_storage(db, tenant_id=tenant_id)
        return approved_invoice
    return update_invoice_status(
        db,
        invoice_id=intake["invoice_id"],
        status="PAID",
        request_ctx=request_ctx or RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing-payment-intake"),
    )


def review_payment_intake(
    db: Session,
    *,
    intake_id: int,
    status: str,
    reviewed_by_admin: str | None,
    review_note: str | None,
) -> dict[str, Any] | None:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return None
    intakes = _table(db, "billing_payment_intakes")
    update_stmt = (
        update(intakes)
        .where(intakes.c.id == intake_id)
        .values(
            status=status,
            reviewed_by_admin=reviewed_by_admin,
            reviewed_at=_now(),
            review_note=review_note,
        )
        .returning(intakes)
    )
    return db.execute(update_stmt).mappings().first()


def mark_payment_intake_status(
    db: Session,
    *,
    intake_id: int,
    status: str,
) -> dict[str, Any] | None:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return None
    intakes = _table(db, "billing_payment_intakes")
    update_stmt = update(intakes).where(intakes.c.id == intake_id).values(status=status).returning(intakes)
    return db.execute(update_stmt).mappings().first()
