from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import MetaData, Table, desc, insert, or_, select, update
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA
from app.models.audit_log import ActorType, AuditVisibility
from app.services.audit_service import AuditService, RequestContext
from app.services.s3_storage import S3Storage
from neft_shared.logging_setup import get_logger

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table as PdfTable
except ImportError:  # pragma: no cover - optional dependency
    A4 = None
    getSampleStyleSheet = SimpleDocTemplate = Spacer = PdfTable = Paragraph = None

logger = get_logger(__name__)


@dataclass(frozen=True)
class SubscriptionInvoiceLine:
    line_type: str
    ref_code: str | None
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


@dataclass(frozen=True)
class SubscriptionInvoiceResult:
    invoice_id: int
    created: bool


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _table_exists(db: Session, name: str) -> bool:
    try:
        from sqlalchemy import inspect

        inspector = inspect(db.get_bind())
        return inspector.has_table(name, schema=DB_SCHEMA)
    except Exception:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _month_bounds(target: date) -> tuple[date, date]:
    first_day = target.replace(day=1)
    prev_month_end = first_day - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    return prev_month_start, prev_month_end


def _add_months(target: date, months: int) -> date:
    month_index = target.month - 1 + months
    year = target.year + month_index // 12
    month = month_index % 12 + 1
    day = min(target.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _year_bounds(target: date) -> tuple[date, date]:
    start = target.replace(day=1)
    end = _add_months(start, 12) - timedelta(days=1)
    return start, end


def _resolve_period(subscription: dict[str, Any], target: date) -> tuple[date, date]:
    cycle = (subscription.get("billing_cycle") or "MONTHLY").upper()
    if cycle == "YEARLY":
        return _year_bounds(target)
    return _month_bounds(target)


def _tables_ready(db: Session, table_names: Iterable[str]) -> bool:
    return all(_table_exists(db, name) for name in table_names)


def _resolve_pricing_record(
    db: Session,
    *,
    item_type: str,
    item_id: int,
    as_of: datetime,
) -> dict[str, Any] | None:
    pricing_catalog = _table(db, "pricing_catalog")
    record = (
        db.execute(
            select(pricing_catalog)
            .where(
                pricing_catalog.c.item_type == item_type,
                pricing_catalog.c.item_id == item_id,
                pricing_catalog.c.effective_from <= as_of,
                or_(pricing_catalog.c.effective_to.is_(None), pricing_catalog.c.effective_to > as_of),
            )
            .order_by(desc(pricing_catalog.c.effective_from))
            .limit(1)
        )
        .mappings()
        .first()
    )
    return dict(record) if record else None


def _plan_line(
    db: Session,
    subscription: dict[str, Any],
    *,
    as_of: datetime,
) -> tuple[SubscriptionInvoiceLine, str | None]:
    subscription_plans = _table(db, "subscription_plans")
    plan = (
        db.execute(select(subscription_plans).where(subscription_plans.c.id == subscription["plan_id"]))
        .mappings()
        .first()
    )
    plan_code = plan.get("code") if plan else None
    description = plan.get("title") if plan else None
    pricing = _resolve_pricing_record(db, item_type="PLAN", item_id=subscription["plan_id"], as_of=as_of) or {}
    cycle = (subscription.get("billing_cycle") or "MONTHLY").upper()
    price = pricing.get("price_yearly") if cycle == "YEARLY" else pricing.get("price_monthly")
    line = SubscriptionInvoiceLine(
        line_type="PLAN",
        ref_code=plan_code,
        description=description or (f"Plan {plan_code}" if plan_code else "Plan"),
        quantity=Decimal("1"),
        unit_price=_decimal(price),
        amount=_decimal(price),
    )
    currency = pricing.get("currency") if pricing else None
    return line, currency


def _addon_lines(
    db: Session,
    subscription_id: int,
) -> list[SubscriptionInvoiceLine]:
    org_addons = _table(db, "org_subscription_addons")
    addons = _table(db, "addons")
    rows = (
        db.execute(
            select(
                addons.c.code,
                addons.c.title,
                addons.c.default_price,
                org_addons.c.price_override,
            )
            .join(addons, addons.c.id == org_addons.c.addon_id)
            .where(
                org_addons.c.org_subscription_id == subscription_id,
                org_addons.c.status == "ACTIVE",
            )
        )
        .mappings()
        .all()
    )
    lines: list[SubscriptionInvoiceLine] = []
    for row in rows:
        unit_price = row.get("price_override")
        if unit_price is None:
            unit_price = row.get("default_price")
        price = _decimal(unit_price)
        lines.append(
            SubscriptionInvoiceLine(
                line_type="ADDON",
                ref_code=row.get("code"),
                description=row.get("title") or row.get("code"),
                quantity=Decimal("1"),
                unit_price=price,
                amount=price,
            )
        )
    return lines


def _invoice_exists(
    db: Session,
    *,
    subscription_id: int,
    period_start: date,
    period_end: date,
) -> bool:
    billing_invoices = _table(db, "billing_invoices")
    existing = (
        db.execute(
            select(billing_invoices.c.id).where(
                billing_invoices.c.subscription_id == subscription_id,
                billing_invoices.c.period_start == period_start,
                billing_invoices.c.period_end == period_end,
            )
        )
        .mappings()
        .first()
    )
    return existing is not None


def _resolve_invoice_currency(
    db: Session,
    *,
    org_id: int,
    fallback: str | None,
) -> str:
    if _table_exists(db, "billing_accounts"):
        billing_accounts = _table(db, "billing_accounts")
        account = (
            db.execute(select(billing_accounts.c.currency).where(billing_accounts.c.org_id == org_id))
            .mappings()
            .first()
        )
        if account and account.get("currency"):
            return str(account["currency"])
    return fallback or "RUB"


def _invoice_lines_total(lines: Iterable[SubscriptionInvoiceLine]) -> Decimal:
    return sum((line.amount for line in lines), Decimal("0"))


def generate_subscription_invoice(
    db: Session,
    *,
    subscription: dict[str, Any],
    period_start: date,
    period_end: date,
    request_ctx: RequestContext | None,
) -> SubscriptionInvoiceResult:
    if _invoice_exists(
        db,
        subscription_id=subscription["id"],
        period_start=period_start,
        period_end=period_end,
    ):
        return SubscriptionInvoiceResult(invoice_id=0, created=False)

    now = _now()
    plan_line, currency = _plan_line(db, subscription, as_of=now)
    addon_lines = _addon_lines(db, subscription["id"]) if _table_exists(db, "org_subscription_addons") else []
    lines = [plan_line, *addon_lines]
    total_amount = _invoice_lines_total(lines)
    currency_code = _resolve_invoice_currency(db, org_id=subscription["org_id"], fallback=currency)
    due_at = now + timedelta(days=int(subscription.get("grace_period_days") or 0))

    billing_invoices = _table(db, "billing_invoices")
    insert_stmt = (
        insert(billing_invoices)
        .values(
            org_id=subscription["org_id"],
            subscription_id=subscription["id"],
            period_start=period_start,
            period_end=period_end,
            status="ISSUED",
            issued_at=now,
            due_at=due_at,
            total_amount=total_amount,
            currency=currency_code,
        )
        .returning(billing_invoices.c.id)
    )
    invoice_id = db.execute(insert_stmt).scalar_one()

    billing_invoice_lines = _table(db, "billing_invoice_lines")
    line_payloads = [
        {
            "invoice_id": invoice_id,
            "line_type": line.line_type,
            "ref_code": line.ref_code,
            "description": line.description,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "amount": line.amount,
        }
        for line in lines
    ]
    if line_payloads:
        db.execute(insert(billing_invoice_lines).values(line_payloads))

    AuditService(db).audit(
        event_type="SUBSCRIPTION_INVOICE_ISSUED",
        entity_type="billing_invoice",
        entity_id=str(invoice_id),
        action="ISSUE",
        after={
            "org_id": subscription["org_id"],
            "subscription_id": subscription["id"],
            "status": "ISSUED",
            "period_start": period_start,
            "period_end": period_end,
            "total_amount": str(total_amount),
            "currency": currency_code,
            "due_at": due_at,
        },
        request_ctx=request_ctx or RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_subscription"),
    )

    return SubscriptionInvoiceResult(invoice_id=invoice_id, created=True)


def generate_invoices_for_period(
    db: Session,
    *,
    target_date: date,
    org_id: int | None = None,
    subscription_id: int | None = None,
    request_ctx: RequestContext | None = None,
) -> list[int]:
    required_tables = [
        "org_subscriptions",
        "subscription_plans",
        "billing_invoices",
        "billing_invoice_lines",
        "pricing_catalog",
    ]
    if not _tables_ready(db, required_tables):
        logger.warning("subscription_billing.tables_missing")
        return []

    org_subscriptions = _table(db, "org_subscriptions")
    query = select(org_subscriptions).where(org_subscriptions.c.status == "ACTIVE")
    if org_id is not None:
        query = query.where(org_subscriptions.c.org_id == org_id)
    if subscription_id is not None:
        query = query.where(org_subscriptions.c.id == subscription_id)

    subscriptions = db.execute(query).mappings().all()
    created_invoice_ids: list[int] = []

    for subscription in subscriptions:
        period_start, period_end = _resolve_period(subscription, target_date)
        result = generate_subscription_invoice(
            db,
            subscription=subscription,
            period_start=period_start,
            period_end=period_end,
            request_ctx=request_ctx,
        )
        if result.created:
            created_invoice_ids.append(result.invoice_id)

    return created_invoice_ids


def mark_invoice_overdue(db: Session, *, now: datetime | None = None) -> list[int]:
    if not _tables_ready(db, ["billing_invoices", "org_subscriptions"]):
        logger.warning("subscription_billing.tables_missing_overdue")
        return []

    now = now or _now()
    billing_invoices = _table(db, "billing_invoices")
    org_subscriptions = _table(db, "org_subscriptions")

    overdue_rows = (
        db.execute(
            select(billing_invoices.c.id, billing_invoices.c.subscription_id)
            .where(
                billing_invoices.c.status == "ISSUED",
                billing_invoices.c.due_at.isnot(None),
                billing_invoices.c.due_at < now,
            )
        )
        .mappings()
        .all()
    )

    overdue_invoice_ids: list[int] = []
    for row in overdue_rows:
        invoice_id = row["id"]
        subscription_id = row["subscription_id"]
        db.execute(
            update(billing_invoices)
            .where(billing_invoices.c.id == invoice_id)
            .values(status="OVERDUE")
        )
        db.execute(
            update(org_subscriptions)
            .where(org_subscriptions.c.id == subscription_id)
            .values(status="OVERDUE")
        )
        AuditService(db).audit(
            event_type="SUBSCRIPTION_INVOICE_OVERDUE",
            entity_type="billing_invoice",
            entity_id=str(invoice_id),
            action="OVERDUE",
            after={"status": "OVERDUE", "subscription_id": subscription_id},
            request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_overdue"),
        )
        overdue_invoice_ids.append(invoice_id)

    return overdue_invoice_ids


def update_invoice_status(
    db: Session,
    *,
    invoice_id: int,
    status: str,
    request_ctx: RequestContext | None,
) -> dict[str, Any] | None:
    if not _tables_ready(db, ["billing_invoices", "org_subscriptions"]):
        logger.warning("subscription_billing.tables_missing_status_update")
        return None

    billing_invoices = _table(db, "billing_invoices")
    org_subscriptions = _table(db, "org_subscriptions")

    invoice = (
        db.execute(select(billing_invoices).where(billing_invoices.c.id == invoice_id))
        .mappings()
        .first()
    )
    if not invoice:
        return None

    updates: dict[str, Any] = {"status": status}
    now = _now()
    if status == "PAID":
        updates["paid_at"] = now
    elif status in {"VOID", "OVERDUE", "ISSUED"}:
        updates["paid_at"] = None

    db.execute(update(billing_invoices).where(billing_invoices.c.id == invoice_id).values(**updates))

    if status == "PAID":
        db.execute(
            update(org_subscriptions)
            .where(org_subscriptions.c.id == invoice["subscription_id"])
            .values(status="ACTIVE")
        )

    AuditService(db).audit(
        event_type=f"SUBSCRIPTION_INVOICE_{status}",
        entity_type="billing_invoice",
        entity_id=str(invoice_id),
        action=status,
        after={"status": status, "subscription_id": invoice["subscription_id"]},
        request_ctx=request_ctx or RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_admin"),
    )

    invoice.update(updates)
    return dict(invoice)


def generate_invoice_pdf(db: Session, *, invoice_id: int) -> bool:
    if any(dep is None for dep in (A4, getSampleStyleSheet, SimpleDocTemplate, Spacer, PdfTable, Paragraph)):
        raise RuntimeError("reportlab is required for PDF generation")

    if not _tables_ready(db, ["billing_invoices", "billing_invoice_lines"]):
        logger.warning("subscription_billing.tables_missing_pdf")
        return False

    billing_invoices = _table(db, "billing_invoices")
    billing_invoice_lines = _table(db, "billing_invoice_lines")
    invoice = (
        db.execute(select(billing_invoices).where(billing_invoices.c.id == invoice_id))
        .mappings()
        .first()
    )
    if not invoice:
        return False

    lines = (
        db.execute(select(billing_invoice_lines).where(billing_invoice_lines.c.invoice_id == invoice_id))
        .mappings()
        .all()
    )

    billing_account = None
    if _table_exists(db, "billing_accounts"):
        billing_accounts = _table(db, "billing_accounts")
        billing_account = (
            db.execute(select(billing_accounts).where(billing_accounts.c.org_id == invoice["org_id"]))
            .mappings()
            .first()
        )

    from io import BytesIO

    payload = BytesIO()
    doc = SimpleDocTemplate(payload, pagesize=A4)
    styles = getSampleStyleSheet()

    org_name = billing_account.get("legal_name") if billing_account else None
    inn = billing_account.get("inn") if billing_account else None
    kpp = billing_account.get("kpp") if billing_account else None

    story = [
        Paragraph("Invoice", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Organization: {org_name or invoice['org_id']}", styles["Normal"]),
    ]
    if inn:
        story.append(Paragraph(f"ИНН: {inn}", styles["Normal"]))
    if kpp:
        story.append(Paragraph(f"КПП: {kpp}", styles["Normal"]))

    story.extend(
        [
            Spacer(1, 12),
            Paragraph(
                f"Period: {invoice['period_start']} — {invoice['period_end']}",
                styles["Normal"],
            ),
            Paragraph(f"Status: {invoice['status']}", styles["Normal"]),
            Paragraph(f"Currency: {invoice['currency']}", styles["Normal"]),
            Spacer(1, 12),
            Paragraph("Lines", styles["Heading2"]),
        ]
    )

    if lines:
        headers = ["Type", "Code", "Description", "Qty", "Unit price", "Amount"]
        rows = [
            [
                line.get("line_type"),
                line.get("ref_code") or "",
                line.get("description") or "",
                str(line.get("quantity") or ""),
                str(line.get("unit_price") or ""),
                str(line.get("amount") or ""),
            ]
            for line in lines
        ]
        table = PdfTable([headers, *rows])
        story.append(table)
    else:
        story.append(Paragraph("No lines", styles["Italic"]))

    story.extend(
        [
            Spacer(1, 12),
            Paragraph(f"Total: {invoice.get('total_amount')}", styles["Normal"]),
            Paragraph("Без НДС", styles["Normal"]),
            Paragraph(f"Generated at: {_now().isoformat()}", styles["Normal"]),
        ]
    )

    doc.build(story)
    pdf_bytes = payload.getvalue()

    storage = S3Storage()
    storage.ensure_bucket()
    key = invoice.get("pdf_object_key") or f"billing-invoices/{invoice_id}.pdf"
    storage.put_bytes(key, pdf_bytes, content_type="application/pdf")

    db.execute(update(billing_invoices).where(billing_invoices.c.id == invoice_id).values(pdf_object_key=key))
    AuditService(db).audit(
        event_type="SUBSCRIPTION_INVOICE_PDF_UPLOADED",
        entity_type="billing_invoice",
        entity_id=str(invoice_id),
        action="PDF",
        visibility=AuditVisibility.INTERNAL,
        after={"pdf_object_key": key},
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_pdf"),
    )
    return True


__all__ = [
    "SubscriptionInvoiceLine",
    "SubscriptionInvoiceResult",
    "generate_invoices_for_period",
    "generate_subscription_invoice",
    "generate_invoice_pdf",
    "mark_invoice_overdue",
    "update_invoice_status",
]
