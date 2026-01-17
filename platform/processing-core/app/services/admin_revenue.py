from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import MetaData, Table, and_, case, desc, func, or_, select, true
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _table_exists(db: Session, name: str) -> bool:
    try:
        from sqlalchemy import inspect

        inspector = inspect(db.get_bind())
        return inspector.has_table(name, schema=DB_SCHEMA)
    except Exception:
        return False


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _as_of_dt(as_of: date) -> datetime:
    return datetime.combine(as_of, time.min, tzinfo=timezone.utc)


def _month_start(as_of: date) -> date:
    return as_of.replace(day=1)


def _load_subscription_overrides(db: Session) -> dict[int, dict[str, Decimal]]:
    if not _table_exists(db, "org_subscription_overrides"):
        return {}
    overrides = _table(db, "org_subscription_overrides")
    if "org_subscription_id" not in overrides.c:
        return {}

    override_columns: list[tuple[str, Any]] = []
    if "price_override" in overrides.c:
        override_columns.append(("price_override", overrides.c.price_override))
    if "price_monthly" in overrides.c:
        override_columns.append(("price_monthly", overrides.c.price_monthly))
    if "price_yearly" in overrides.c:
        override_columns.append(("price_yearly", overrides.c.price_yearly))

    if not override_columns:
        return {}

    columns = [
        overrides.c.org_subscription_id.label("subscription_id"),
        *[func.max(column).label(name) for name, column in override_columns],
    ]
    query = select(*columns).group_by(overrides.c.org_subscription_id)
    rows = db.execute(query).mappings().all()
    overrides_map: dict[int, dict[str, Decimal]] = {}
    for row in rows:
        payload = {
            name: _decimal(row.get(name)) if row.get(name) is not None else None
            for name, _ in override_columns
        }
        overrides_map[int(row["subscription_id"])] = {k: v for k, v in payload.items() if v is not None}
    return overrides_map


def _resolve_plan_price(row: dict[str, Any], overrides: dict[int, dict[str, Decimal]]) -> tuple[Decimal | None, str | None]:
    billing_cycle = (row.get("billing_cycle") or "MONTHLY").upper()
    price_monthly = row.get("price_monthly")
    price_yearly = row.get("price_yearly")
    price: Decimal | None
    if billing_cycle == "YEARLY":
        price = _decimal(price_yearly) / Decimal("12") if price_yearly is not None else None
    else:
        price = _decimal(price_monthly) if price_monthly is not None else None

    if price is None:
        override = overrides.get(int(row["subscription_id"]))
        if override:
            if override.get("price_override") is not None:
                price = override["price_override"]
            elif billing_cycle == "YEARLY" and override.get("price_yearly") is not None:
                price = override["price_yearly"] / Decimal("12")
            elif override.get("price_monthly") is not None:
                price = override["price_monthly"]

    currency = row.get("currency")
    return price, currency


def _plan_rows(db: Session, as_of: date) -> list[dict[str, Any]]:
    if not _table_exists(db, "org_subscriptions"):
        return []
    if not _table_exists(db, "pricing_catalog"):
        return []

    org_subscriptions = _table(db, "org_subscriptions")
    subscription_plans = _table(db, "subscription_plans") if _table_exists(db, "subscription_plans") else None
    pricing_catalog = _table(db, "pricing_catalog")
    as_of_dt = _as_of_dt(as_of)

    pricing_lateral = (
        select(
            pricing_catalog.c.price_monthly,
            pricing_catalog.c.price_yearly,
            pricing_catalog.c.currency,
        )
        .where(
            pricing_catalog.c.item_type == "PLAN",
            pricing_catalog.c.item_id == org_subscriptions.c.plan_id,
            pricing_catalog.c.effective_from <= as_of_dt,
            or_(pricing_catalog.c.effective_to.is_(None), pricing_catalog.c.effective_to > as_of_dt),
        )
        .order_by(desc(pricing_catalog.c.effective_from))
        .limit(1)
        .lateral("plan_pricing")
    )

    query = select(
        org_subscriptions.c.id.label("subscription_id"),
        org_subscriptions.c.org_id,
        org_subscriptions.c.status,
        org_subscriptions.c.billing_cycle,
        org_subscriptions.c.plan_id,
        pricing_lateral.c.price_monthly,
        pricing_lateral.c.price_yearly,
        pricing_lateral.c.currency,
    )
    if subscription_plans is not None:
        query = query.add_columns(subscription_plans.c.code.label("plan_code"))
        query = query.select_from(
            org_subscriptions.join(subscription_plans, subscription_plans.c.id == org_subscriptions.c.plan_id, isouter=True)
            .join(pricing_lateral, true(), isouter=True)
        )
    else:
        query = query.select_from(org_subscriptions.join(pricing_lateral, true(), isouter=True))
    query = query.where(org_subscriptions.c.status == "ACTIVE")
    return [dict(row) for row in db.execute(query).mappings().all()]


def revenue_summary(db: Session, *, as_of: date) -> dict[str, Any]:
    active_orgs = 0
    overdue_orgs = 0
    overdue_amount = Decimal("0")
    usage_revenue_mtd = Decimal("0")
    plan_mix: list[dict[str, Any]] = []
    addon_mix: list[dict[str, Any]] = []
    overdue_buckets: list[dict[str, Any]] = []
    mrr_amount = Decimal("0")
    currency = "RUB"

    if _table_exists(db, "org_subscriptions"):
        org_subscriptions = _table(db, "org_subscriptions")
        active_orgs = db.execute(
            select(func.count(func.distinct(org_subscriptions.c.org_id))).where(org_subscriptions.c.status == "ACTIVE")
        ).scalar_one()
        overdue_orgs = db.execute(
            select(func.count(func.distinct(org_subscriptions.c.org_id))).where(org_subscriptions.c.status == "OVERDUE")
        ).scalar_one()

    plan_rows = _plan_rows(db, as_of)
    overrides = _load_subscription_overrides(db)
    plan_mix_map: dict[str, dict[str, Any]] = {}
    for row in plan_rows:
        plan_code = row.get("plan_code") or "UNKNOWN"
        plan_entry = plan_mix_map.setdefault(plan_code, {"orgs": set(), "mrr": Decimal("0"), "missing": False})
        plan_entry["orgs"].add(row["org_id"])
        price, row_currency = _resolve_plan_price(row, overrides)
        if row_currency:
            currency = row_currency
        if price is None:
            plan_entry["missing"] = True
            continue
        plan_entry["mrr"] += price
        mrr_amount += price

    for plan_code, data in sorted(plan_mix_map.items()):
        plan_mix.append(
            {
                "plan": plan_code,
                "orgs": len(data["orgs"]),
                "mrr": None if data["missing"] else data["mrr"],
            }
        )

    if _table_exists(db, "org_subscription_addons") and _table_exists(db, "addons") and _table_exists(db, "org_subscriptions"):
        org_addons = _table(db, "org_subscription_addons")
        addons = _table(db, "addons")
        org_subscriptions = _table(db, "org_subscriptions")
        addon_price = func.coalesce(org_addons.c.price_override, addons.c.default_price)
        rows = (
            db.execute(
                select(
                    addons.c.code.label("addon_code"),
                    func.count(func.distinct(org_subscriptions.c.org_id)).label("orgs"),
                    func.coalesce(func.sum(addon_price), 0).label("mrr"),
                )
                .join(org_subscriptions, org_subscriptions.c.id == org_addons.c.org_subscription_id)
                .join(addons, addons.c.id == org_addons.c.addon_id)
                .where(org_addons.c.status == "ACTIVE", org_subscriptions.c.status == "ACTIVE")
                .group_by(addons.c.code)
                .order_by(addons.c.code)
            )
            .mappings()
            .all()
        )
        for row in rows:
            addon_mix.append(
                {
                    "addon": row["addon_code"],
                    "orgs": int(row["orgs"]),
                    "mrr": _decimal(row["mrr"]),
                }
            )
            mrr_amount += _decimal(row["mrr"])

    if _table_exists(db, "billing_invoices"):
        billing_invoices = _table(db, "billing_invoices")
        overdue_amount = _decimal(
            db.execute(
                select(func.coalesce(func.sum(billing_invoices.c.total_amount), 0)).where(
                    billing_invoices.c.status == "OVERDUE"
                )
            ).scalar_one()
        )
        as_of_dt = _as_of_dt(as_of)
        bucket_case = case(
            (billing_invoices.c.due_at >= as_of_dt - timedelta(days=7), "0_7"),
            (billing_invoices.c.due_at >= as_of_dt - timedelta(days=30), "8_30"),
            (billing_invoices.c.due_at >= as_of_dt - timedelta(days=90), "31_90"),
            else_="90_plus",
        )
        bucket_rows = (
            db.execute(
                select(
                    bucket_case.label("bucket"),
                    func.count(func.distinct(billing_invoices.c.org_id)).label("orgs"),
                    func.coalesce(func.sum(billing_invoices.c.total_amount), 0).label("amount"),
                )
                .where(
                    billing_invoices.c.status == "OVERDUE",
                    billing_invoices.c.due_at.isnot(None),
                    billing_invoices.c.due_at <= as_of_dt,
                )
                .group_by(bucket_case)
            )
            .mappings()
            .all()
        )
        bucket_labels = {
            "0_7": "0–7 дней",
            "8_30": "8–30 дней",
            "31_90": "31–90 дней",
            "90_plus": "90+ дней",
        }
        bucket_map = {row["bucket"]: row for row in bucket_rows}
        overdue_buckets = [
            {
                "bucket": key,
                "label": bucket_labels[key],
                "orgs": int(bucket_map.get(key, {}).get("orgs", 0) or 0),
                "amount": _decimal(bucket_map.get(key, {}).get("amount", 0)),
            }
            for key in ("0_7", "8_30", "31_90", "90_plus")
        ]

    if _table_exists(db, "billing_invoices") and _table_exists(db, "billing_invoice_lines"):
        billing_invoices = _table(db, "billing_invoices")
        billing_invoice_lines = _table(db, "billing_invoice_lines")
        month_start = _month_start(as_of)
        usage_revenue_mtd = _decimal(
            db.execute(
                select(func.coalesce(func.sum(billing_invoice_lines.c.amount), 0))
                .join(billing_invoices, billing_invoices.c.id == billing_invoice_lines.c.invoice_id)
                .where(
                    billing_invoice_lines.c.line_type == "USAGE",
                    billing_invoices.c.period_start >= month_start,
                    billing_invoices.c.period_start <= as_of,
                )
            ).scalar_one()
        )

    arr_amount = mrr_amount * Decimal("12")
    return {
        "as_of": as_of,
        "mrr": {"amount": mrr_amount, "currency": currency},
        "arr": {"amount": arr_amount, "currency": currency},
        "active_orgs": active_orgs,
        "overdue_orgs": overdue_orgs,
        "overdue_amount": overdue_amount,
        "usage_revenue_mtd": usage_revenue_mtd,
        "plan_mix": plan_mix,
        "addon_mix": addon_mix,
        "overdue_buckets": overdue_buckets,
    }


def _apply_overdue_bucket_filter(query, *, bucket: str, as_of_dt: datetime, due_at_column):
    lower = None
    upper = None
    if bucket == "0_7":
        lower = as_of_dt - timedelta(days=7)
        upper = as_of_dt
    elif bucket == "8_30":
        lower = as_of_dt - timedelta(days=30)
        upper = as_of_dt - timedelta(days=7)
    elif bucket == "31_90":
        lower = as_of_dt - timedelta(days=90)
        upper = as_of_dt - timedelta(days=30)
    elif bucket == "90_plus":
        upper = as_of_dt - timedelta(days=90)
    else:
        return query

    conditions = [due_at_column.isnot(None), due_at_column <= as_of_dt]
    if lower is not None:
        conditions.append(due_at_column > lower)
    if upper is not None:
        conditions.append(due_at_column <= upper)
    return query.where(and_(*conditions))


def revenue_overdue_list(
    db: Session,
    *,
    as_of: date,
    bucket: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    if not _table_exists(db, "billing_invoices"):
        return [], 0

    billing_invoices = _table(db, "billing_invoices")
    as_of_dt = _as_of_dt(as_of)
    base = select(
        billing_invoices.c.id.label("invoice_id"),
        billing_invoices.c.org_id,
        billing_invoices.c.subscription_id,
        billing_invoices.c.due_at,
        billing_invoices.c.total_amount,
        billing_invoices.c.currency,
        func.row_number()
        .over(partition_by=billing_invoices.c.org_id, order_by=desc(billing_invoices.c.due_at))
        .label("rn"),
    ).where(billing_invoices.c.status == "OVERDUE")
    base = _apply_overdue_bucket_filter(base, bucket=bucket, as_of_dt=as_of_dt, due_at_column=billing_invoices.c.due_at)
    base_subq = base.subquery("overdue_ranked")

    query = select(base_subq).where(base_subq.c.rn == 1)

    orgs = None
    if _table_exists(db, "orgs"):
        orgs = _table(db, "orgs")
        if "id" in orgs.c:
            query = query.add_columns(orgs.c.name.label("org_name"))
            query = query.select_from(query.froms[0].outerjoin(orgs, orgs.c.id == base_subq.c.org_id))

    org_subscriptions = None
    if _table_exists(db, "org_subscriptions"):
        org_subscriptions = _table(db, "org_subscriptions")
        query = query.add_columns(
            org_subscriptions.c.status.label("subscription_status"),
            org_subscriptions.c.plan_id.label("plan_id"),
        )
        query = query.select_from(
            query.froms[0].outerjoin(org_subscriptions, org_subscriptions.c.id == base_subq.c.subscription_id)
        )

    if org_subscriptions is not None and _table_exists(db, "subscription_plans"):
        subscription_plans = _table(db, "subscription_plans")
        query = query.add_columns(subscription_plans.c.code.label("plan_code"))
        query = query.select_from(
            query.froms[0].outerjoin(subscription_plans, subscription_plans.c.id == org_subscriptions.c.plan_id)
        )

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = (
        db.execute(query.order_by(base_subq.c.due_at.asc()).limit(limit).offset(offset))
        .mappings()
        .all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        due_at = row.get("due_at")
        overdue_days = 0
        if due_at:
            overdue_days = (as_of_dt.date() - due_at.date()).days
        items.append(
            {
                "org_id": row.get("org_id"),
                "org_name": row.get("org_name"),
                "invoice_id": str(row.get("invoice_id")),
                "due_at": due_at,
                "overdue_days": max(overdue_days, 0),
                "amount": _decimal(row.get("total_amount")),
                "currency": row.get("currency"),
                "subscription_plan": row.get("plan_code"),
                "subscription_status": row.get("subscription_status"),
            }
        )
    return items, int(total)


def revenue_usage_totals(db: Session, *, period_from: date, period_to: date) -> list[dict[str, Any]]:
    if not (_table_exists(db, "billing_invoices") and _table_exists(db, "billing_invoice_lines")):
        return []

    billing_invoices = _table(db, "billing_invoices")
    billing_invoice_lines = _table(db, "billing_invoice_lines")
    rows = (
        db.execute(
            select(
                billing_invoice_lines.c.ref_code.label("ref_code"),
                func.coalesce(func.sum(billing_invoice_lines.c.quantity), 0).label("quantity"),
                func.coalesce(func.sum(billing_invoice_lines.c.amount), 0).label("amount"),
            )
            .join(billing_invoices, billing_invoices.c.id == billing_invoice_lines.c.invoice_id)
            .where(
                billing_invoice_lines.c.line_type == "USAGE",
                billing_invoices.c.period_start >= period_from,
                billing_invoices.c.period_start <= period_to,
            )
            .group_by(billing_invoice_lines.c.ref_code)
            .order_by(func.coalesce(func.sum(billing_invoice_lines.c.amount), 0).desc())
        )
        .mappings()
        .all()
    )
    return [
        {
            "ref_code": row.get("ref_code"),
            "quantity": _decimal(row.get("quantity")),
            "amount": _decimal(row.get("amount")),
        }
        for row in rows
    ]


__all__ = [
    "revenue_summary",
    "revenue_overdue_list",
    "revenue_usage_totals",
]
