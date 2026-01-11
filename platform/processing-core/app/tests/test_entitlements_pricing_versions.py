from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.db import get_sessionmaker
from app.db.schema import DB_SCHEMA
from app.models.contract_limits import TariffPlan, TariffPrice
from app.services.pricing_service import get_effective_price


def _truncate_pricing_tables(db) -> None:
    db.execute(text(f"TRUNCATE {DB_SCHEMA}.tariff_prices CASCADE"))
    db.execute(text(f"TRUNCATE {DB_SCHEMA}.tariff_plans CASCADE"))
    db.commit()


@pytest.fixture()
def db_session():
    session = get_sessionmaker()()
    _truncate_pricing_tables(session)
    try:
        yield session
    finally:
        _truncate_pricing_tables(session)
        session.close()


def test_effective_price_picks_latest_version(db_session):
    plan = TariffPlan(id="T-001", name="Plan A")
    db_session.add(plan)
    db_session.commit()

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    today = datetime.now(timezone.utc)

    db_session.add(
        TariffPrice(
            tariff_id="T-001",
            product_id="DIESEL",
            price_per_liter=Decimal("10.0"),
            cost_price_per_liter=Decimal("7.0"),
            currency="RUB",
            valid_from=yesterday,
            priority=100,
        )
    )
    db_session.add(
        TariffPrice(
            tariff_id="T-001",
            product_id="DIESEL",
            price_per_liter=Decimal("11.0"),
            cost_price_per_liter=Decimal("7.5"),
            currency="RUB",
            valid_from=today,
            priority=100,
        )
    )
    db_session.commit()

    quote = get_effective_price(
        db_session,
        tariff_id="T-001",
        product_id="DIESEL",
        occurred_at=today + timedelta(hours=1),
    )

    assert quote.tariff_price.price_per_liter == Decimal("11.0")
