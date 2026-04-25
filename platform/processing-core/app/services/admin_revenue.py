from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import MetaData, String, Table, and_, case, cast, desc, func, literal, or_, select
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


def _column(table: Table, *names: str):
    for name in names:
        if name in table.c:
            return table.c[name]
    return None


def _invoice_amount_expr(billing_invoices: Table):
    amount_due = _column(billing_invoices, "amount_due")
    if amount_due is not None:
        return func.coalesce(amount_due, 0)

    total_amount = _column(billing_invoices, "total_amount")
    if total_amount is not None:
        return func.coalesce(total_amount, 0)

    total_with_tax = _column(billing_invoices, "total_with_tax")
    amount_paid = _column(billing_invoices, "amount_paid")
    if total_with_tax is not None:
        total_expr = func.coalesce(total_with_tax, 0)
        if amount_paid is not None:
            return total_expr - func.coalesce(amount_paid, 0)
        return total_expr

    amount_total = _column(billing_invoices, "amount_total")
    if amount_total is not None:
        total_expr = func.coalesce(amount_total, 0)
        if amount_paid is not None:
            return total_expr - func.coalesce(amount_paid, 0)
        return total_expr

    subtotal = _column(billing_invoices, "subtotal")
    if subtotal is not None:
        return func.coalesce(subtotal, 0)
    return literal(0)


def _status_value_supported(status_col, value: str) -> bool:
    enum_values = getattr(getattr(status_col, "type", None), "enums", None)
    if enum_values is None:
        return True
    return value in {str(item) for item in enum_values}


def _invoice_status_overdue_condition(
    billing_invoices: Table,
    *,
    amount_expr,
    as_of_dt: datetime,
):
    status_col = _column(billing_invoices, "status")
    if status_col is None:
        return literal(False)

    due_at_col = _column(billing_invoices, "due_at")
    conditions = []
    if _status_value_supported(status_col, "OVERDUE"):
        conditions.append(status_col == "OVERDUE")

    open_status_values = tuple(
        value for value in ("ISSUED", "PARTIALLY_PAID") if _status_value_supported(status_col, value)
    )
    if due_at_col is not None and open_status_values:
        open_status = status_col.in_(open_status_values)
        due_elapsed = and_(due_at_col.isnot(None), due_at_col <= as_of_dt)
        conditions.append(and_(open_status, due_elapsed, amount_expr > 0))

    if not conditions:
        return literal(False)
    return or_(*conditions)


def _invoice_period_column(billing_invoices: Table):
    return _column(billing_invoices, "period_start", "issued_at", "created_at")


def _period_bounds_for_column(period_column, *, period_from: date, period_to: date):
    if period_column is not None and period_column.name == "period_start":
        return period_from, period_to
    return (
        datetime.combine(period_from, time.min, tzinfo=timezone.utc),
        datetime.combine(period_to, time.max, tzinfo=timezone.utc),
    )


def _client_subscription_org_expr(db: Session, billing_invoices: Table):
    client_id_col = _column(billing_invoices, "client_id")
    if client_id_col is None or not _table_exists(db, "client_subscriptions"):
        return None

    client_subscriptions = _table(db, "client_subscriptions")
    tenant_col = _column(client_subscriptions, "tenant_id")
    subscription_client_col = _column(client_subscriptions, "client_id")
    if tenant_col is None or subscription_client_col is None:
        return None

    query = select(tenant_col).where(cast(subscription_client_col, String) == cast(client_id_col, String))
    status_col = _column(client_subscriptions, "status")
    if status_col is not None:
        query = query.order_by(case((status_col == "ACTIVE", 0), else_=1))
    created_at_col = _column(client_subscriptions, "created_at", "start_at")
    if created_at_col is not None:
        query = query.order_by(desc(created_at_col))
    return query.limit(1).scalar_subquery()


def _org_table_client_expr(db: Session, billing_invoices: Table):
    client_id_col = _column(billing_invoices, "client_id")
    if client_id_col is None or not _table_exists(db, "orgs"):
        return None

    orgs = _table(db, "orgs")
    org_id_col = _column(orgs, "id")
    org_client_col = _column(orgs, "client_id", "client_uuid")
    if org_id_col is None or org_client_col is None:
        return None

    return (
        select(org_id_col)
        .where(cast(org_client_col, String) == cast(client_id_col, String))
        .order_by(desc(org_id_col))
        .limit(1)
        .scalar_subquery()
    )


def _invoice_owner_expr(db: Session, billing_invoices: Table):
    org_id_col = _column(billing_invoices, "org_id")
    if org_id_col is not None:
        return org_id_col

    from_orgs = _org_table_client_expr(db, billing_invoices)
    if from_orgs is not None:
        return from_orgs
    return _client_subscription_org_expr(db, billing_invoices)


def _invoice_owner_count_expr(db: Session, billing_invoices: Table):
    owner_expr = _invoice_owner_expr(db, billing_invoices)
    if owner_expr is not None:
        return owner_expr
    return _column(billing_invoices, "client_id", "id")


def _client_plan_rows(db: Session) -> list[dict[str, Any]]:
    if not (_table_exists(db, "client_subscriptions") and _table_exists(db, "subscription_plans")):
        return []

    client_subscriptions = _table(db, "client_subscriptions")
    subscription_plans = _table(db, "subscription_plans")
    required = (
        _column(client_subscriptions, "id"),
        _column(client_subscriptions, "tenant_id"),
        _column(client_subscriptions, "status"),
        _column(client_subscriptions, "plan_id"),
        _column(subscription_plans, "id"),
        _column(subscription_plans, "code"),
    )
    if any(column is None for column in required):
        return []

    price_cents = _column(subscription_plans, "price_cents")
    price_monthly = (func.coalesce(price_cents, 0) / Decimal("100")) if price_cents is not None else literal(None)
    currency_col = _column(subscription_plans, "currency")
    billing_cycle_col = _column(client_subscriptions, "billing_cycle")

    query = (
        select(
            client_subscriptions.c.id.label("subscription_id"),
            client_subscriptions.c.tenant_id.label("org_id"),
            client_subscriptions.c.status,
            (billing_cycle_col if billing_cycle_col is not None else literal("MONTHLY")).label("billing_cycle"),
            client_subscriptions.c.plan_id,
            price_monthly.label("price_monthly"),
            literal(None).label("price_yearly"),
            (currency_col if currency_col is not None else literal("RUB")).label("currency"),
            subscription_plans.c.code.label("plan_code"),
        )
        .select_from(
            client_subscriptions.join(subscription_plans, subscription_plans.c.id == client_subscriptions.c.plan_id)
        )
        .where(client_subscriptions.c.status == "ACTIVE")
    )
    return [dict(row) for row in db.execute(query).mappings().all()]


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
        try:
            subscription_id = int(row["subscription_id"])
        except (TypeError, ValueError):
            subscription_id = None
        override = overrides.get(subscription_id) if subscription_id is not None else None
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
        return _client_plan_rows(db)
    if not _table_exists(db, "pricing_catalog"):
        return _client_plan_rows(db)

    org_subscriptions = _table(db, "org_subscriptions")
    subscription_plans = _table(db, "subscription_plans") if _table_exists(db, "subscription_plans") else None
    pricing_catalog = _table(db, "pricing_catalog")
    as_of_dt = _as_of_dt(as_of)

    plan_code_col = subscription_plans.c.code if subscription_plans is not None else literal("UNKNOWN")
    from_clause = org_subscriptions
    if subscription_plans is not None:
        from_clause = from_clause.outerjoin(subscription_plans, subscription_plans.c.id == org_subscriptions.c.plan_id)
    from_clause = from_clause.outerjoin(
        pricing_catalog,
        and_(
            pricing_catalog.c.item_type == "PLAN",
            pricing_catalog.c.item_id == org_subscriptions.c.plan_id,
            pricing_catalog.c.effective_from <= as_of_dt,
            or_(pricing_catalog.c.effective_to.is_(None), pricing_catalog.c.effective_to > as_of_dt),
        ),
    )

    ranked = (
        select(
            org_subscriptions.c.id.label("subscription_id"),
            org_subscriptions.c.org_id,
            org_subscriptions.c.status,
            org_subscriptions.c.billing_cycle,
            org_subscriptions.c.plan_id,
            pricing_catalog.c.price_monthly,
            pricing_catalog.c.price_yearly,
            pricing_catalog.c.currency,
            plan_code_col.label("plan_code"),
            func.row_number()
            .over(partition_by=org_subscriptions.c.id, order_by=desc(pricing_catalog.c.effective_from))
            .label("_pricing_rank"),
        )
        .select_from(from_clause)
        .where(org_subscriptions.c.status == "ACTIVE")
        .subquery("ranked_plan_pricing")
    )

    query = select(
        ranked.c.subscription_id,
        ranked.c.org_id,
        ranked.c.status,
        ranked.c.billing_cycle,
        ranked.c.plan_id,
        ranked.c.price_monthly,
        ranked.c.price_yearly,
        ranked.c.currency,
        ranked.c.plan_code,
    ).where(ranked.c._pricing_rank == 1)
    rows = [dict(row) for row in db.execute(query).mappings().all()]
    return rows or _client_plan_rows(db)


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
    elif _table_exists(db, "client_subscriptions"):
        client_subscriptions = _table(db, "client_subscriptions")
        tenant_col = _column(client_subscriptions, "tenant_id")
        status_col = _column(client_subscriptions, "status")
        if tenant_col is not None and status_col is not None:
            active_orgs = db.execute(
                select(func.count(func.distinct(tenant_col))).where(status_col == "ACTIVE")
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
        amount_expr = _invoice_amount_expr(billing_invoices)
        as_of_dt = _as_of_dt(as_of)
        overdue_condition = _invoice_status_overdue_condition(
            billing_invoices,
            amount_expr=amount_expr,
            as_of_dt=as_of_dt,
        )
        owner_count_expr = _invoice_owner_count_expr(db, billing_invoices)
        overdue_amount = _decimal(
            db.execute(
                select(func.coalesce(func.sum(amount_expr), 0)).where(overdue_condition)
            ).scalar_one()
        )
        if owner_count_expr is not None:
            overdue_orgs = int(
                db.execute(select(func.count(func.distinct(owner_count_expr))).where(overdue_condition)).scalar_one()
                or 0
            )
        due_at_col = _column(billing_invoices, "due_at")
        bucket_rows: list[dict[str, Any]] = []
        if due_at_col is not None and owner_count_expr is not None:
            bucket_case = case(
                (due_at_col >= as_of_dt - timedelta(days=7), "0_7"),
                (due_at_col >= as_of_dt - timedelta(days=30), "8_30"),
                (due_at_col >= as_of_dt - timedelta(days=90), "31_90"),
                else_="90_plus",
            )
            bucket_rows = (
                db.execute(
                    select(
                        bucket_case.label("bucket"),
                        func.count(func.distinct(owner_count_expr)).label("orgs"),
                        func.coalesce(func.sum(amount_expr), 0).label("amount"),
                    )
                    .where(
                        overdue_condition,
                        due_at_col.isnot(None),
                        due_at_col <= as_of_dt,
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
        period_col = _invoice_period_column(billing_invoices)
        line_amount_col = _column(billing_invoice_lines, "amount")
        line_type_col = _column(billing_invoice_lines, "line_type")
        invoice_id_col = _column(billing_invoice_lines, "invoice_id")
        billing_invoice_id_col = _column(billing_invoices, "id")
        if (
            period_col is not None
            and line_amount_col is not None
            and line_type_col is not None
            and invoice_id_col is not None
            and billing_invoice_id_col is not None
        ):
            lower_bound, upper_bound = _period_bounds_for_column(
                period_col,
                period_from=month_start,
                period_to=as_of,
            )
            usage_revenue_mtd = _decimal(
                db.execute(
                    select(func.coalesce(func.sum(line_amount_col), 0))
                    .join(billing_invoices, billing_invoice_id_col == invoice_id_col)
                    .where(
                        line_type_col == "USAGE",
                        period_col >= lower_bound,
                        period_col <= upper_bound,
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
    amount_expr = _invoice_amount_expr(billing_invoices)
    overdue_condition = _invoice_status_overdue_condition(
        billing_invoices,
        amount_expr=amount_expr,
        as_of_dt=as_of_dt,
    )
    owner_expr = _invoice_owner_expr(db, billing_invoices)
    if owner_expr is None:
        return [], 0
    invoice_id_col = _column(billing_invoices, "id")
    due_at_col = _column(billing_invoices, "due_at")
    currency_col = _column(billing_invoices, "currency")
    subscription_id_col = _column(billing_invoices, "subscription_id")
    if invoice_id_col is None:
        return [], 0

    order_col = due_at_col if due_at_col is not None else invoice_id_col
    base = select(
        invoice_id_col.label("invoice_id"),
        owner_expr.label("org_id"),
        (subscription_id_col if subscription_id_col is not None else literal(None)).label("subscription_id"),
        (due_at_col if due_at_col is not None else literal(None)).label("due_at"),
        amount_expr.label("amount"),
        (currency_col if currency_col is not None else literal(None)).label("currency"),
        func.row_number()
        .over(partition_by=owner_expr, order_by=desc(order_col))
        .label("rn"),
    ).where(overdue_condition, owner_expr.isnot(None))
    if due_at_col is not None:
        base = _apply_overdue_bucket_filter(base, bucket=bucket, as_of_dt=as_of_dt, due_at_column=due_at_col)
    base_subq = base.subquery("overdue_ranked")

    from_clause = base_subq
    columns = [base_subq]

    orgs = None
    if _table_exists(db, "orgs"):
        orgs = _table(db, "orgs")
        if "id" in orgs.c:
            columns.append(orgs.c.name.label("org_name"))
            from_clause = from_clause.outerjoin(orgs, orgs.c.id == base_subq.c.org_id)

    org_subscriptions = None
    if _table_exists(db, "org_subscriptions"):
        org_subscriptions = _table(db, "org_subscriptions")
        columns.extend(
            [
                org_subscriptions.c.status.label("subscription_status"),
                org_subscriptions.c.plan_id.label("plan_id"),
            ]
        )
        from_clause = from_clause.outerjoin(org_subscriptions, org_subscriptions.c.id == base_subq.c.subscription_id)

    if org_subscriptions is not None and _table_exists(db, "subscription_plans"):
        subscription_plans = _table(db, "subscription_plans")
        columns.append(subscription_plans.c.code.label("plan_code"))
        from_clause = from_clause.outerjoin(subscription_plans, subscription_plans.c.id == org_subscriptions.c.plan_id)

    query = select(*columns).select_from(from_clause).where(base_subq.c.rn == 1)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = (
        db.execute(query.order_by(base_subq.c.due_at.asc()).limit(limit).offset(offset))
        .mappings()
        .all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        try:
            org_id = int(row.get("org_id"))
        except (TypeError, ValueError):
            continue
        due_at = row.get("due_at")
        overdue_days = 0
        if due_at:
            overdue_days = (as_of_dt.date() - due_at.date()).days
        items.append(
            {
                "org_id": org_id,
                "org_name": row.get("org_name"),
                "invoice_id": str(row.get("invoice_id")),
                "due_at": due_at,
                "overdue_days": max(overdue_days, 0),
                "amount": _decimal(row.get("amount")),
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
    period_col = _invoice_period_column(billing_invoices)
    invoice_id_col = _column(billing_invoice_lines, "invoice_id")
    billing_invoice_id_col = _column(billing_invoices, "id")
    line_type_col = _column(billing_invoice_lines, "line_type")
    amount_col = _column(billing_invoice_lines, "amount")
    quantity_col = _column(billing_invoice_lines, "quantity")
    ref_code_col = _column(billing_invoice_lines, "ref_code")
    if (
        period_col is None
        or invoice_id_col is None
        or billing_invoice_id_col is None
        or line_type_col is None
        or amount_col is None
    ):
        return []
    lower_bound, upper_bound = _period_bounds_for_column(
        period_col,
        period_from=period_from,
        period_to=period_to,
    )
    rows = (
        db.execute(
            select(
                (ref_code_col if ref_code_col is not None else literal(None)).label("ref_code"),
                func.coalesce(func.sum(quantity_col if quantity_col is not None else literal(0)), 0).label("quantity"),
                func.coalesce(func.sum(amount_col), 0).label("amount"),
            )
            .join(billing_invoices, billing_invoice_id_col == invoice_id_col)
            .where(
                line_type_col == "USAGE",
                period_col >= lower_bound,
                period_col <= upper_bound,
            )
            .group_by(ref_code_col if ref_code_col is not None else literal(None))
            .order_by(func.coalesce(func.sum(amount_col), 0).desc())
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
