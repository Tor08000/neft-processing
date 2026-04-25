from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.contract_limits import TariffPlan, TariffPrice
from app.services.pricing_service import get_effective_price
from app.tests._money_router_harness import money_session_context


PRICING_TEST_TABLES = (
    TariffPlan.__table__,
    TariffPrice.__table__,
)


@pytest.fixture
def session():
    with money_session_context(tables=PRICING_TEST_TABLES) as db:
        yield db


def _add_tariff_price(
    db,
    *,
    tariff_id: str,
    product_id: str,
    price: str,
    currency: str = "RUB",
    partner_id: str | None = None,
    azs_id: str | None = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    priority: int = 100,
    cost_price: str | None = None,
) -> TariffPrice:
    obj = TariffPrice(
        tariff_id=tariff_id,
        product_id=product_id,
        partner_id=partner_id,
        azs_id=azs_id,
        price_per_liter=Decimal(price),
        cost_price_per_liter=Decimal(cost_price) if cost_price else None,
        currency=currency,
        valid_from=valid_from,
        valid_to=valid_to,
        priority=priority,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_partner_price_takes_precedence(session):
    now = datetime.now(timezone.utc)
    session.add(TariffPlan(id="tariff-1", name="Base"))
    session.commit()

    general = _add_tariff_price(
        session,
        tariff_id="tariff-1",
        product_id="AI95",
        price="50.000",
        valid_from=now - timedelta(days=1),
    )
    partner_specific = _add_tariff_price(
        session,
        tariff_id="tariff-1",
        product_id="AI95",
        partner_id="partner-1",
        price="45.500",
        priority=50,
        valid_from=now - timedelta(hours=2),
    )

    quote = get_effective_price(
        session,
        tariff_id="tariff-1",
        product_id="AI95",
        partner_id="partner-1",
        azs_id=None,
        occurred_at=now,
    )

    assert quote.tariff_price.id == partner_specific.id
    assert quote.client_price_per_liter == Decimal("45.500")

    fallback = get_effective_price(
        session,
        tariff_id="tariff-1",
        product_id="AI95",
        partner_id="unknown",
        azs_id=None,
        occurred_at=now,
    )

    assert fallback.tariff_price.id == general.id


def test_latest_valid_price_used(session):
    now = datetime.now(timezone.utc)
    session.add(TariffPlan(id="tariff-2", name="Premium"))
    session.commit()

    old_price = _add_tariff_price(
        session,
        tariff_id="tariff-2",
        product_id="DIESEL",
        price="48.000",
        valid_from=now - timedelta(days=3),
        valid_to=now - timedelta(days=1),
    )
    current_price = _add_tariff_price(
        session,
        tariff_id="tariff-2",
        product_id="DIESEL",
        price="49.000",
        valid_from=now - timedelta(hours=5),
    )

    quote = get_effective_price(
        session,
        tariff_id="tariff-2",
        product_id="DIESEL",
        partner_id=None,
        azs_id="azs-1",
        occurred_at=now - timedelta(hours=1),
    )

    assert quote.tariff_price.id == current_price.id
    assert quote.client_price_per_liter == Decimal("49.000")

    with pytest.raises(ValueError):
        get_effective_price(
            session,
            tariff_id="tariff-2",
            product_id="DIESEL",
            partner_id=None,
            azs_id=None,
            occurred_at=old_price.valid_from - timedelta(days=1),
        )
