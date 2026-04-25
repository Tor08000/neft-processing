from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.client import Client
from app.models.contract_limits import ClientTariff, CommissionRule, TariffPlan, TariffPrice
from app.services.tariffs.resolver import resolve_tariff_snapshot


TARIFF_RESOLVER_TEST_TABLES = (
    TariffPlan.__table__,
    TariffPrice.__table__,
    ClientTariff.__table__,
    CommissionRule.__table__,
    Client.__table__,
)


@pytest.fixture
def session():
    stub_metadata = MetaData()
    Table("fleet_offline_profiles", stub_metadata, Column("id", String(36), primary_key=True))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    stub_metadata.create_all(bind=engine)
    for table in TARIFF_RESOLVER_TEST_TABLES:
        table.create(bind=engine, checkfirst=True)

    db = Session(bind=engine, expire_on_commit=False)
    try:
        yield db
    finally:
        db.close()
        for table in reversed(TARIFF_RESOLVER_TEST_TABLES):
            table.drop(bind=engine, checkfirst=True)
        stub_metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()


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
) -> TariffPrice:
    obj = TariffPrice(
        tariff_id=tariff_id,
        product_id=product_id,
        partner_id=partner_id,
        azs_id=azs_id,
        price_per_liter=Decimal(price),
        currency=currency,
        valid_from=valid_from,
        valid_to=valid_to,
        priority=priority,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def test_resolves_tariff_and_price_from_assignment(session):
    now = datetime.now(timezone.utc)
    session.add_all([TariffPlan(id="T1", name="Base"), TariffPlan(id="T2", name="Premium")])
    client_id = uuid4()
    session.add(Client(id=client_id, name="Test", status="ACTIVE"))
    session.add(ClientTariff(client_id=str(client_id), tariff_id="T2", priority=10))
    session.commit()
    _add_tariff_price(session, tariff_id="T2", product_id="AI95", price="50.000", valid_from=now - timedelta(days=1))

    snapshot = resolve_tariff_snapshot(
        session,
        client_id=str(client_id),
        partner_id=None,
        azs_id=None,
        product_id="AI95",
        occurred_at=now,
    )

    assert snapshot.tariff_id == "T2"
    assert snapshot.unit_price == Decimal("50.000")
    assert "client_tariff" in ":".join(snapshot.trace)
    assert snapshot.commission.platform_rate > 0


def test_commission_rule_priority_and_scope(session):
    now = datetime.now(timezone.utc)
    session.add(TariffPlan(id="T-main", name="Main"))
    client_id = uuid4()
    session.add(Client(id=client_id, name="Test", status="ACTIVE", tariff_plan="T-main"))
    session.commit()
    _add_tariff_price(session, tariff_id="T-main", product_id="DIESEL", price="60.000", valid_from=now - timedelta(days=1))

    session.add(
        CommissionRule(
            tariff_id="T-main",
            product_id="DIESEL",
            partner_id=None,
            azs_id=None,
            platform_rate=Decimal("0.0500"),
            partner_rate=None,
            promo_rate=None,
            priority=200,
        )
    )
    session.add(
        CommissionRule(
            tariff_id="T-main",
            product_id="DIESEL",
            partner_id="partner-1",
            azs_id=None,
            platform_rate=Decimal("0.0300"),
            partner_rate=Decimal("0.0100"),
            promo_rate=None,
            priority=50,
        )
    )
    session.commit()

    snapshot = resolve_tariff_snapshot(
        session,
        client_id=str(client_id),
        partner_id="partner-1",
        azs_id=None,
        product_id="DIESEL",
        occurred_at=now,
    )

    assert snapshot.commission.commission_rule_id is not None
    assert snapshot.commission.platform_rate == Decimal("0.0300")
    assert snapshot.commission.partner_rate == Decimal("0.0100")
    assert "commission.partner" in ":".join(snapshot.trace)


def test_falls_back_to_default_commission(session):
    now = datetime.now(timezone.utc)
    session.add(TariffPlan(id="T-basic", name="Basic"))
    client_id = uuid4()
    session.add(Client(id=client_id, name="Test", status="ACTIVE", tariff_plan="T-basic"))
    session.commit()
    _add_tariff_price(session, tariff_id="T-basic", product_id="GAS", price="30.000", valid_from=now - timedelta(days=1))
    session.commit()

    snapshot = resolve_tariff_snapshot(
        session,
        client_id=str(client_id),
        partner_id=None,
        azs_id=None,
        product_id="GAS",
        occurred_at=now,
    )

    assert snapshot.commission.source == "DEFAULT_COMMISSION"
    assert snapshot.commission.commission_rule_id is None
    assert "commission.default" in snapshot.trace
