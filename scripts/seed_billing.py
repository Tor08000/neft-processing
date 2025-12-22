#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSING_ROOT = ROOT / "platform" / "processing-core"
SHARED = ROOT / "shared" / "python"

for path in (PROCESSING_ROOT, SHARED):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.db import get_sessionmaker, init_db  # noqa: E402
from app.services.demo_seed import DemoSeeder  # noqa: E402


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
        print(json.dumps(result, indent=2, sort_keys=True))

    try:
        asyncio.run(_bootstrap_admin())
    except Exception:
        pass


if __name__ == "__main__":
    main()
