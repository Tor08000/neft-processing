from __future__ import annotations

import calendar
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import MetaData, Table, desc, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA
from app.models.audit_log import ActorType, AuditVisibility
from app.services.billing_service import issue_invoice
from app.services.audit_service import AuditService, RequestContext
from app.services.case_events_service import CaseEventActor
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
SubscriptionInvoiceId = str | int


@dataclass(frozen=True)
class SubscriptionInvoiceLine:
    line_type: str
    ref_code: str | None
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    meta_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class SubscriptionInvoiceResult:
    invoice_id: SubscriptionInvoiceId
    created: bool


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=_bind(db), schema=DB_SCHEMA)


def _bind(db: Session):
    try:
        return db.connection()
    except Exception:
        return db.get_bind()


def _table_exists(db: Session, name: str) -> bool:
    try:
        from sqlalchemy import inspect

        inspector = inspect(_bind(db))
        return inspector.has_table(name, schema=DB_SCHEMA)
    except Exception:
        return False


def _has_columns(table: Table, *columns: str) -> bool:
    available = set(table.c.keys())
    return all(column in available for column in columns)


def _is_billing_flow_invoice_table(table: Table) -> bool:
    return _has_columns(
        table,
        "client_id",
        "invoice_number",
        "amount_total",
        "amount_paid",
        "idempotency_key",
        "ledger_tx_id",
        "audit_event_id",
    )


def _is_legacy_subscription_invoice_table(table: Table) -> bool:
    return _has_columns(table, "subscription_id", "period_start", "period_end")


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


def _invoice_table_invoice_exists(db: Session, *, invoice_id: SubscriptionInvoiceId) -> bool:
    if not _table_exists(db, "invoices"):
        return False
    invoices = _table(db, "invoices")
    return (
        db.execute(select(invoices.c.id).where(invoices.c.id == str(invoice_id)))
        .scalar_one_or_none()
        is not None
    )


def _generate_invoice_table_invoice_pdf(db: Session, *, invoice_id: SubscriptionInvoiceId) -> bool:
    from app.models.invoice import Invoice
    from app.services.invoice_pdf import InvoicePdfService

    invoice = db.get(Invoice, str(invoice_id))
    if invoice is None:
        return False
    InvoicePdfService(db).generate(invoice)
    return True


def _billing_flow_invoice_row(db: Session, *, invoice_id: SubscriptionInvoiceId) -> dict[str, Any] | None:
    if not _table_exists(db, "billing_invoices"):
        return None
    billing_invoices = _table(db, "billing_invoices")
    if not _is_billing_flow_invoice_table(billing_invoices) or _is_legacy_subscription_invoice_table(billing_invoices):
        return None
    row = (
        db.execute(select(billing_invoices).where(billing_invoices.c.id == str(invoice_id)))
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _period_label_from_idempotency_key(idempotency_key: object) -> str:
    parts = str(idempotency_key or "").split(":")
    if len(parts) >= 4 and parts[0] == "subscription-invoice":
        return f"{parts[-2]} - {parts[-1]}"
    return "not specified"


def _generate_billing_flow_invoice_pdf(
    db: Session,
    *,
    invoice_id: SubscriptionInvoiceId,
    invoice: dict[str, Any] | None = None,
) -> bool:
    billing_invoices = _table(db, "billing_invoices")
    required_columns = {"pdf_status", "pdf_object_key", "pdf_url", "pdf_hash", "pdf_generated_at"}
    missing_columns = sorted(required_columns.difference(billing_invoices.c.keys()))
    if missing_columns:
        logger.warning(
            "subscription_billing.billing_flow_pdf_columns_missing",
            extra={"invoice_id": str(invoice_id), "missing_columns": missing_columns},
        )
        return False

    invoice = invoice or _billing_flow_invoice_row(db, invoice_id=invoice_id)
    if not invoice:
        return False

    from io import BytesIO

    payload = BytesIO()
    doc = SimpleDocTemplate(payload, pagesize=A4)
    styles = getSampleStyleSheet()
    amount_total = _decimal(invoice.get("amount_total"))
    amount_paid = _decimal(invoice.get("amount_paid"))
    amount_due = amount_total - amount_paid
    period_label = _period_label_from_idempotency_key(invoice.get("idempotency_key"))
    invoice_number = invoice.get("invoice_number") or str(invoice_id)
    currency = invoice.get("currency") or ""

    story = [
        Paragraph("NEFT Billing Invoice", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Invoice: {invoice_number}", styles["Normal"]),
        Paragraph(f"Client: {invoice.get('client_id')}", styles["Normal"]),
        Paragraph(f"Period: {period_label}", styles["Normal"]),
        Paragraph(f"Status: {invoice.get('status')}", styles["Normal"]),
        Paragraph(f"Currency: {currency}", styles["Normal"]),
        Spacer(1, 12),
        PdfTable(
            [
                ["Description", "Amount", "Paid", "Due"],
                ["Subscription charge", str(amount_total), str(amount_paid), str(amount_due)],
            ]
        ),
        Spacer(1, 12),
        Paragraph(f"Generated at: {_now().isoformat()}", styles["Normal"]),
    ]
    doc.build(story)
    pdf_bytes = payload.getvalue()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    storage = S3Storage()
    storage.ensure_bucket()
    key = invoice.get("pdf_object_key") or f"billing-invoices/{invoice_id}.pdf"
    pdf_url = storage.put_bytes(key, pdf_bytes, content_type="application/pdf")
    db.execute(
        update(billing_invoices)
        .where(billing_invoices.c.id == invoice["id"])
        .values(
            pdf_status="READY",
            pdf_object_key=key,
            pdf_url=pdf_url,
            pdf_hash=pdf_hash,
            pdf_generated_at=_now(),
        )
    )
    AuditService(db).audit(
        event_type="BILLING_FLOW_INVOICE_PDF_UPLOADED",
        entity_type="billing_invoice",
        entity_id=str(invoice_id),
        action="PDF",
        visibility=AuditVisibility.INTERNAL,
        after={"pdf_object_key": key, "pdf_url": pdf_url, "pdf_hash": pdf_hash},
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_pdf"),
    )
    return True


def _normalize_subscription_status(status: str | None) -> str | None:
    if not status:
        return None
    upper = str(status).upper()
    if upper == "OVERDUE":
        return "PAST_DUE"
    return upper


def _legacy_billing_cycle(plan: dict[str, Any] | None) -> str:
    if not plan:
        return "MONTHLY"
    try:
        months = int(plan.get("billing_period_months") or 0)
    except (TypeError, ValueError):
        return "MONTHLY"
    if months == 12:
        return "YEARLY"
    return "MONTHLY"


def _legacy_subscription_rows(
    db: Session,
    *,
    org_id: int | None = None,
    subscription_id: int | None = None,
) -> list[dict[str, Any]]:
    required_tables = [
        "client_subscriptions",
        "subscription_plans",
        "billing_invoices",
    ]
    if not _tables_ready(db, required_tables):
        return []
    client_subscriptions = _table(db, "client_subscriptions")
    subscription_plans = _table(db, "subscription_plans")
    query = select(client_subscriptions)
    if org_id is not None:
        query = query.where(client_subscriptions.c.tenant_id == org_id)
    if subscription_id is not None:
        query = query.where(client_subscriptions.c.id == subscription_id)
    query = query.where(client_subscriptions.c.status == "ACTIVE")
    rows = db.execute(query).mappings().all()
    plan_ids = {row["plan_id"] for row in rows if row.get("plan_id") is not None}
    plans: dict[Any, dict[str, Any]] = {}
    if plan_ids:
        plan_rows = (
            db.execute(select(subscription_plans).where(subscription_plans.c.id.in_(plan_ids)))
            .mappings()
            .all()
        )
        plans = {row["id"]: dict(row) for row in plan_rows}
    subscriptions: list[dict[str, Any]] = []
    for row in rows:
        plan = plans.get(row.get("plan_id"))
        subscriptions.append(
            {
                **dict(row),
                "org_id": row.get("tenant_id"),
                "billing_cycle": _legacy_billing_cycle(plan),
                "grace_period_days": 0,
                "_storage": "client_subscriptions",
            }
        )
    return subscriptions


def _resolve_subscription_client_id(db: Session, subscription: dict[str, Any]) -> str | None:
    client_id = subscription.get("client_id")
    if client_id not in (None, ""):
        return str(client_id)
    if not _table_exists(db, "client_subscriptions"):
        return None

    client_subscriptions = _table(db, "client_subscriptions")
    client_id_column = client_subscriptions.c.get("client_id")
    if client_id_column is None:
        return None

    subscription_id = subscription.get("id")
    if subscription_id not in (None, "") and client_subscriptions.c.get("id") is not None:
        resolved = (
            db.execute(select(client_id_column).where(client_subscriptions.c.id == subscription_id))
            .scalar()
        )
        if resolved not in (None, ""):
            return str(resolved)

    tenant_id = subscription.get("org_id")
    if tenant_id in (None, "") or client_subscriptions.c.get("tenant_id") is None:
        return None

    query = select(client_id_column).where(client_subscriptions.c.tenant_id == tenant_id)
    order_by = []
    if client_subscriptions.c.get("created_at") is not None:
        order_by.append(desc(client_subscriptions.c.created_at))
    elif client_subscriptions.c.get("start_at") is not None:
        order_by.append(desc(client_subscriptions.c.start_at))
    if order_by:
        query = query.order_by(*order_by)
    resolved = db.execute(query.limit(1)).scalar()
    if resolved in (None, ""):
        return None
    return str(resolved)


def _update_legacy_subscription_status(
    db: Session,
    *,
    invoice: dict[str, Any],
    status: str,
) -> None:
    if not _table_exists(db, "client_subscriptions"):
        return
    client_subscriptions = _table(db, "client_subscriptions")
    target_status = _normalize_subscription_status(status)
    subscription_id = invoice.get("subscription_id")
    if subscription_id is not None:
        result = db.execute(
            update(client_subscriptions)
            .where(client_subscriptions.c.id == subscription_id)
            .values(status=target_status)
        )
        if getattr(result, "rowcount", 0):
            return
    org_id = invoice.get("org_id")
    if org_id is None:
        return
    db.execute(
        update(client_subscriptions)
        .where(client_subscriptions.c.tenant_id == org_id)
        .values(status=target_status)
    )


def _resolve_pricing_record(
    db: Session,
    *,
    item_type: str,
    item_id: int,
    as_of: datetime,
) -> dict[str, Any] | None:
    if not _table_exists(db, "pricing_catalog"):
        return None
    pricing_catalog = _table(db, "pricing_catalog")
    resolved_item_id = _coerce_pricing_catalog_item_id(pricing_catalog.c.item_id, item_id)
    if resolved_item_id is None:
        return None
    record = (
        db.execute(
            select(pricing_catalog)
            .where(
                pricing_catalog.c.item_type == item_type,
                pricing_catalog.c.item_id == resolved_item_id,
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


def _coerce_pricing_catalog_item_id(column, item_id: Any) -> Any:
    try:
        python_type = column.type.python_type
    except Exception:
        python_type = None

    if python_type is int:
        if isinstance(item_id, int):
            return item_id
        if isinstance(item_id, str):
            normalized = item_id.strip()
            if normalized.isdigit():
                return int(normalized)
            return None
        try:
            return int(item_id)
        except (TypeError, ValueError):
            return None
    return item_id


def _billing_flow_invoice_idempotency_key(
    *,
    subscription: dict[str, Any],
    period_start: date,
    period_end: date,
) -> str:
    subscription_ref = subscription.get("id") or subscription.get("client_id") or subscription.get("org_id") or "subscription"
    return f"subscription-invoice:{subscription_ref}:{period_start.isoformat()}:{period_end.isoformat()}"


def _request_ctx_to_case_actor(request_ctx: RequestContext | None) -> CaseEventActor | None:
    if request_ctx is None:
        return None
    if request_ctx.actor_id is None and request_ctx.actor_email is None:
        return None
    return CaseEventActor(id=request_ctx.actor_id, email=request_ctx.actor_email)


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
    if price is None and plan:
        price_cents = plan.get("price_cents")
        if price_cents is not None:
            price = Decimal(str(price_cents)) / Decimal("100")
    line = SubscriptionInvoiceLine(
        line_type="PLAN",
        ref_code=plan_code,
        description=description or (f"Plan {plan_code}" if plan_code else "Plan"),
        quantity=Decimal("1"),
        unit_price=_decimal(price),
        amount=_decimal(price),
    )
    currency = pricing.get("currency") if pricing else None
    if not currency and plan:
        currency = plan.get("currency")
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
    if not _is_legacy_subscription_invoice_table(billing_invoices):
        return False
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


def _billing_flow_invoice_by_idempotency_key(
    db: Session,
    *,
    idempotency_key: str,
) -> dict[str, Any] | None:
    billing_invoices = _table(db, "billing_invoices")
    if not _is_billing_flow_invoice_table(billing_invoices):
        return None
    key_column = billing_invoices.c.get("idempotency_key")
    if key_column is None:
        return None
    row = (
        db.execute(select(billing_invoices).where(key_column == idempotency_key))
        .mappings()
        .first()
    )
    return dict(row) if row else None


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


def _usage_event_bounds(period_start: date, period_end: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(period_start, time.min).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)
    return start_dt, end_dt


def _upsert_usage_aggregate(
    db: Session,
    *,
    org_id: int,
    meter_id: int,
    period_start: date,
    period_end: date,
    quantity: Decimal,
    now: datetime,
) -> None:
    usage_aggregates = _table(db, "usage_aggregates")
    if db.get_bind().dialect.name == "postgresql":
        stmt = (
            pg_insert(usage_aggregates)
            .values(
                org_id=org_id,
                meter_id=meter_id,
                period_start=period_start,
                period_end=period_end,
                quantity=quantity,
                created_at=now,
            )
            .on_conflict_do_update(
                index_elements=["org_id", "meter_id", "period_start", "period_end"],
                set_={"quantity": quantity, "created_at": now},
            )
        )
        db.execute(stmt)
        return
    existing = (
        db.execute(
            select(usage_aggregates.c.id).where(
                usage_aggregates.c.org_id == org_id,
                usage_aggregates.c.meter_id == meter_id,
                usage_aggregates.c.period_start == period_start,
                usage_aggregates.c.period_end == period_end,
            )
        )
        .mappings()
        .first()
    )
    if existing:
        db.execute(
            update(usage_aggregates)
            .where(usage_aggregates.c.id == existing["id"])
            .values(quantity=quantity, created_at=now)
        )
    else:
        db.execute(
            insert(usage_aggregates).values(
                org_id=org_id,
                meter_id=meter_id,
                period_start=period_start,
                period_end=period_end,
                quantity=quantity,
                created_at=now,
            )
        )


def _usage_lines(
    db: Session,
    *,
    org_id: int,
    period_start: date,
    period_end: date,
    as_of: datetime,
) -> tuple[list[SubscriptionInvoiceLine], list[dict[str, Any]], list[dict[str, Any]]]:
    required_tables = ["usage_events", "usage_meters", "pricing_catalog", "usage_aggregates"]
    if not _tables_ready(db, required_tables):
        return [], [], []

    usage_events = _table(db, "usage_events")
    start_dt, end_dt = _usage_event_bounds(period_start, period_end)
    aggregates = (
        db.execute(
            select(
                usage_events.c.meter_id,
                func.coalesce(func.sum(usage_events.c.quantity), 0).label("quantity"),
            )
            .where(
                usage_events.c.org_id == org_id,
                usage_events.c.occurred_at >= start_dt,
                usage_events.c.occurred_at < end_dt,
            )
            .group_by(usage_events.c.meter_id)
        )
        .mappings()
        .all()
    )
    if not aggregates:
        return [], [], []

    meter_ids = [row["meter_id"] for row in aggregates]
    usage_meters = _table(db, "usage_meters")
    meter_rows = (
        db.execute(select(usage_meters).where(usage_meters.c.id.in_(meter_ids))).mappings().all()
    )
    meter_map = {row["id"]: row for row in meter_rows}

    lines: list[SubscriptionInvoiceLine] = []
    summary: list[dict[str, Any]] = []
    missing_pricing: list[dict[str, Any]] = []
    for row in aggregates:
        quantity = _decimal(row.get("quantity"))
        if quantity <= 0:
            continue
        meter = meter_map.get(row["meter_id"])
        if not meter:
            continue
        pricing = _resolve_pricing_record(db, item_type="USAGE_METER", item_id=meter["id"], as_of=as_of)
        if not pricing or pricing.get("price_monthly") is None:
            logger.warning(
                "subscription_billing.usage_pricing_missing",
                extra={"meter_id": meter["id"], "meter_code": meter.get("code")},
            )
            missing_pricing.append(
                {
                    "meter_id": meter.get("id"),
                    "code": meter.get("code"),
                }
            )
            continue
        unit_price = _decimal(pricing.get("price_monthly"))
        currency = pricing.get("currency") if pricing else None
        title = meter.get("title") or meter.get("code") or "Usage"
        unit = meter.get("unit") or ""
        unit_label = f" {unit}" if unit else ""
        description = f"{title}: {quantity}{unit_label} × {unit_price} {currency or 'RUB'}"
        amount = quantity * unit_price
        lines.append(
            SubscriptionInvoiceLine(
                line_type="USAGE",
                ref_code=meter.get("code"),
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                amount=amount,
                meta_json={
                    "meter_id": meter.get("id"),
                    "unit": unit,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                },
            )
        )
        summary.append(
            {
                "meter_id": meter.get("id"),
                "code": meter.get("code"),
                "unit": unit,
                "quantity": str(quantity),
                "unit_price": str(unit_price),
                "amount": str(amount),
            }
        )
        _upsert_usage_aggregate(
            db,
            org_id=org_id,
            meter_id=meter["id"],
            period_start=period_start,
            period_end=period_end,
            quantity=quantity,
            now=as_of,
        )
    return lines, summary, missing_pricing


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
    usage_lines, usage_summary, missing_pricing = _usage_lines(
        db,
        org_id=subscription["org_id"],
        period_start=period_start,
        period_end=period_end,
        as_of=now,
    )
    lines = [plan_line, *addon_lines, *usage_lines]
    total_amount = _invoice_lines_total(lines)
    currency_code = _resolve_invoice_currency(db, org_id=subscription["org_id"], fallback=currency)
    due_at = now + timedelta(days=int(subscription.get("grace_period_days") or 0))
    if total_amount <= 0:
        logger.info(
            "subscription_billing.zero_total_skipped",
            extra={
                "org_id": subscription.get("org_id"),
                "subscription_id": subscription.get("id"),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )
        return SubscriptionInvoiceResult(invoice_id=0, created=False)

    billing_invoices = _table(db, "billing_invoices")
    billing_flow_mode = _is_billing_flow_invoice_table(billing_invoices) and not _is_legacy_subscription_invoice_table(billing_invoices)
    if billing_flow_mode:
        client_id = _resolve_subscription_client_id(db, subscription)
        if client_id in (None, ""):
            logger.warning(
                "subscription_billing.client_id_missing",
                extra={"org_id": subscription.get("org_id"), "subscription_id": subscription.get("id")},
            )
            return SubscriptionInvoiceResult(invoice_id=0, created=False)
        idempotency_key = _billing_flow_invoice_idempotency_key(
            subscription=subscription,
            period_start=period_start,
            period_end=period_end,
        )
        existing_billing_flow_invoice = _billing_flow_invoice_by_idempotency_key(
            db,
            idempotency_key=idempotency_key,
        )
        if existing_billing_flow_invoice is not None:
            logger.info(
                "subscription_billing.billing_flow_invoice_replay",
                extra={
                    "org_id": subscription.get("org_id"),
                    "subscription_id": subscription.get("id"),
                    "invoice_id": existing_billing_flow_invoice.get("id"),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                },
            )
            return SubscriptionInvoiceResult(
                invoice_id=str(existing_billing_flow_invoice["id"]),
                created=False,
            )
        issued = issue_invoice(
            db,
            tenant_id=int(subscription["org_id"]),
            client_id=str(client_id),
            case_id=None,
            currency=currency_code,
            amount_total=total_amount,
            due_at=due_at,
            idempotency_key=idempotency_key,
            actor=_request_ctx_to_case_actor(request_ctx),
            request_id=request_ctx.request_id if request_ctx else None,
            trace_id=request_ctx.trace_id if request_ctx else None,
        )
        invoice_id: SubscriptionInvoiceId = str(issued.invoice.id)
        if issued.is_replay:
            return SubscriptionInvoiceResult(invoice_id=invoice_id, created=False)
    else:
        insert_values = {
            "org_id": subscription["org_id"],
            "subscription_id": subscription["id"],
            "period_start": period_start,
            "period_end": period_end,
            "status": "ISSUED",
            "issued_at": now,
            "due_at": due_at,
            "total_amount": total_amount,
            "currency": currency_code,
        }
        insert_stmt = insert(billing_invoices).values(**insert_values)
        if _bind(db).dialect.name == "sqlite":
            result = db.execute(insert_stmt)
            invoice_id = int(result.inserted_primary_key[0])
        else:
            invoice_id = db.execute(insert_stmt.returning(billing_invoices.c.id)).scalar_one()

    line_payloads = [
        {
            "invoice_id": invoice_id,
            "line_type": line.line_type,
            "ref_code": line.ref_code,
            "description": line.description,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "amount": line.amount,
            "meta_json": line.meta_json,
        }
        for line in lines
    ]
    if line_payloads and _table_exists(db, "billing_invoice_lines"):
        billing_invoice_lines = _table(db, "billing_invoice_lines")
        db.execute(insert(billing_invoice_lines).values(line_payloads))

    if usage_summary:
        AuditService(db).audit(
            event_type="USAGE_INVOICED",
            entity_type="billing_invoice",
            entity_id=str(invoice_id),
            action="USAGE_INVOICED",
            after={
                "org_id": subscription["org_id"],
                "subscription_id": subscription["id"],
                "period_start": period_start,
                "period_end": period_end,
                "meters": usage_summary,
            },
            request_ctx=request_ctx or RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_subscription"),
        )

    if missing_pricing:
        AuditService(db).audit(
            event_type="USAGE_PRICING_MISSING",
            entity_type="billing_invoice",
            entity_id=str(invoice_id),
            action="WARN",
            after={
                "org_id": subscription["org_id"],
                "subscription_id": subscription["id"],
                "period_start": period_start,
                "period_end": period_end,
                "meters": missing_pricing,
            },
            request_ctx=request_ctx or RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_subscription"),
        )

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
) -> list[SubscriptionInvoiceId]:
    if _tables_ready(
        db,
        [
            "org_subscriptions",
            "subscription_plans",
            "billing_invoices",
            "billing_invoice_lines",
            "pricing_catalog",
        ],
    ):
        org_subscriptions = _table(db, "org_subscriptions")
        query = select(org_subscriptions).where(org_subscriptions.c.status == "ACTIVE")
        if org_id is not None:
            query = query.where(org_subscriptions.c.org_id == org_id)
        if subscription_id is not None:
            query = query.where(org_subscriptions.c.id == subscription_id)
        subscriptions = [dict(row) for row in db.execute(query).mappings().all()]
    else:
        subscriptions = _legacy_subscription_rows(
            db,
            org_id=org_id,
            subscription_id=subscription_id,
        )

    if not subscriptions:
        logger.warning("subscription_billing.tables_missing")
        return []

    created_invoice_ids: list[SubscriptionInvoiceId] = []

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
    if not _tables_ready(db, ["billing_invoices"]):
        logger.warning("subscription_billing.tables_missing_overdue")
        return []

    now = now or _now()
    billing_invoices = _table(db, "billing_invoices")
    org_subscriptions = _table(db, "org_subscriptions") if _table_exists(db, "org_subscriptions") else None

    overdue_rows = (
        db.execute(
            select(billing_invoices.c.id, billing_invoices.c.subscription_id, billing_invoices.c.org_id)
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
        if org_subscriptions is not None:
            db.execute(
                update(org_subscriptions)
                .where(org_subscriptions.c.id == subscription_id)
                .values(status="OVERDUE")
            )
        else:
            _update_legacy_subscription_status(db, invoice=row, status="OVERDUE")
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
    if not _tables_ready(db, ["billing_invoices"]):
        logger.warning("subscription_billing.tables_missing_status_update")
        return None

    billing_invoices = _table(db, "billing_invoices")
    org_subscriptions = _table(db, "org_subscriptions") if _table_exists(db, "org_subscriptions") else None

    invoice = (
        db.execute(select(billing_invoices).where(billing_invoices.c.id == invoice_id))
        .mappings()
        .first()
    )
    if not invoice:
        return None
    invoice = dict(invoice)

    updates: dict[str, Any] = {"status": status}
    now = _now()
    if status == "PAID":
        updates["paid_at"] = now
    elif status in {"VOID", "OVERDUE", "ISSUED"}:
        updates["paid_at"] = None

    db.execute(update(billing_invoices).where(billing_invoices.c.id == invoice_id).values(**updates))

    if status == "PAID":
        if org_subscriptions is not None:
            db.execute(
                update(org_subscriptions)
                .where(org_subscriptions.c.id == invoice["subscription_id"])
                .values(status="ACTIVE")
            )
        else:
            _update_legacy_subscription_status(db, invoice=invoice, status="ACTIVE")

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


def generate_invoice_pdf(db: Session, *, invoice_id: SubscriptionInvoiceId) -> bool:
    if any(dep is None for dep in (A4, getSampleStyleSheet, SimpleDocTemplate, Spacer, PdfTable, Paragraph)):
        raise RuntimeError("reportlab is required for PDF generation")

    billing_flow_invoice = _billing_flow_invoice_row(db, invoice_id=invoice_id)
    if billing_flow_invoice is not None:
        return _generate_billing_flow_invoice_pdf(db, invoice_id=invoice_id, invoice=billing_flow_invoice)

    if _invoice_table_invoice_exists(db, invoice_id=invoice_id):
        return _generate_invoice_table_invoice_pdf(db, invoice_id=invoice_id)

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
