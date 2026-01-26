#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSING_ROOT = ROOT / "platform" / "processing-core"
SHARED = ROOT / "shared" / "python"

for path in (PROCESSING_ROOT, SHARED):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.db import get_sessionmaker, init_db  # noqa: E402
from sqlalchemy import MetaData, Table, inspect, select, update  # noqa: E402

from app.db.schema import DB_SCHEMA  # noqa: E402
from app.services.demo_seed import DemoSeeder  # noqa: E402


def _table(session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=session.get_bind(), schema=DB_SCHEMA)


def _table_exists(session, name: str) -> bool:
    inspector = inspect(session.get_bind())
    return inspector.has_table(name, schema=DB_SCHEMA)


def _seed_overdue_invoice(session) -> dict[str, str]:
    if not _table_exists(session, "billing_invoices"):
        return {"status": "skipped_missing_billing_invoices"}
    if not _table_exists(session, "org_subscriptions"):
        return {"status": "skipped_missing_org_subscriptions"}
    billing_invoices = _table(session, "billing_invoices")
    org_subscriptions = _table(session, "org_subscriptions")

    invoice = (
        session.execute(select(billing_invoices).order_by(billing_invoices.c.issued_at.desc()))
        .mappings()
        .first()
    )
    if not invoice:
        return {"status": "skipped_no_invoice"}

    overdue_at = datetime.now(timezone.utc) - timedelta(days=7)
    update_payload = {"status": "OVERDUE"}
    if "due_at" in billing_invoices.c:
        update_payload["due_at"] = overdue_at
    if "paid_at" in billing_invoices.c:
        update_payload["paid_at"] = None
    session.execute(update(billing_invoices).where(billing_invoices.c.id == invoice["id"]).values(**update_payload))

    if invoice.get("subscription_id"):
        session.execute(
            update(org_subscriptions)
            .where(org_subscriptions.c.id == invoice["subscription_id"])
            .values(status="OVERDUE")
        )
    session.commit()
    return {"status": "overdue_seeded", "invoice_id": str(invoice["id"])}


async def _bootstrap_admin() -> None:
    """Best-effort bootstrap of auth admin for smoke/demo."""

    try:
        sys.path.insert(0, str(ROOT / "platform" / "auth-host"))
        from app.bootstrap import bootstrap_admin_account  # type: ignore
        from app.settings import Settings  # type: ignore
    except Exception:
        return

    try:
        await bootstrap_admin_account(settings=Settings())
    except Exception:
        # auth DB might be unavailable in local runs; continue seeding core data
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo billing data")
    parser.add_argument(
        "--date",
        type=str,
        help="Billing date (YYYY-MM-DD). Defaults to yesterday.",
    )
    args = parser.parse_args()

    init_db()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        seeder = DemoSeeder(session)
        billing_date = date.fromisoformat(args.date) if args.date else None
        result = seeder.seed(billing_date=billing_date)
        result["overdue_seed"] = _seed_overdue_invoice(session)
        print(json.dumps(result, indent=2, sort_keys=True))

    try:
        asyncio.run(_bootstrap_admin())
    except Exception:
        pass


if __name__ == "__main__":
    main()
