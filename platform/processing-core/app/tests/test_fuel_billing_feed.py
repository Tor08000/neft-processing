from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4

import pytest

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelStation
from app.models.billing_summary import BillingSummary
from app.schemas.fuel import FuelAuthorizeRequest
from app.services.billing.daily import run_billing_daily
from app.services.fuel.authorize import authorize_fuel_tx
from app.services.fuel.settlement import settle_fuel_tx


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_refs(db):
    network = FuelNetwork(id=str(uuid4()), name="NET-1", provider_code="net-1", status="ACTIVE")
    station = FuelStation(
        id=str(uuid4()),
        network_id=network.id,
        name="Station",
        country="RU",
        region="SPB",
        city="SPB",
        station_code="ST-1",
        status="ACTIVE",
    )
    vehicle = FleetVehicle(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        plate_number="A123BC",
        tank_capacity_liters=60,
        status=FleetVehicleStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-token-1",
        status=FuelCardStatus.ACTIVE,
        vehicle_id=vehicle.id,
    )
    db.add_all([network, station, vehicle, card])
    db.commit()


def test_settled_fuel_tx_aggregated(session):
    _seed_refs(session)
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=5.0,
        unit_price=100,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate="A123BC",
    )
    result = authorize_fuel_tx(session, payload=payload)
    tx_id = result.response.transaction_id
    settle_fuel_tx(session, transaction_id=tx_id)

    summaries = run_billing_daily(
        target_date=datetime.now(timezone.utc).date(),
        session=session,
    )

    assert summaries
    assert session.query(BillingSummary).count() > 0


def test_reversed_fuel_tx_excluded(session):
    _seed_refs(session)
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=5.0,
        unit_price=100,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate="A123BC",
    )
    result = authorize_fuel_tx(session, payload=payload)
    tx_id = result.response.transaction_id
    settle_fuel_tx(session, transaction_id=tx_id)
    from app.services.fuel.settlement import reverse_fuel_tx

    reverse_fuel_tx(session, transaction_id=tx_id)

    summaries = run_billing_daily(
        target_date=datetime.now(timezone.utc).date(),
        session=session,
    )

    assert summaries == []


def test_billing_boundary_excludes_next_day(session):
    _seed_refs(session)
    billing_tz = ZoneInfo(settings.NEFT_BILLING_TZ)
    billing_date = datetime.now(timezone.utc).astimezone(billing_tz).date()
    end_of_day = datetime.combine(billing_date, time(23, 59, 59)).replace(tzinfo=billing_tz)
    end_of_day_utc = end_of_day.astimezone(timezone.utc)
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=end_of_day_utc,
        fuel_type="DIESEL",
        volume_liters=5.0,
        unit_price=100,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate="A123BC",
    )
    result = authorize_fuel_tx(session, payload=payload)
    settle_fuel_tx(session, transaction_id=result.response.transaction_id)

    payload_next = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=end_of_day_utc + timedelta(seconds=2),
        fuel_type="DIESEL",
        volume_liters=5.0,
        unit_price=100,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate="A123BC",
    )
    result_next = authorize_fuel_tx(session, payload=payload_next)
    settle_fuel_tx(session, transaction_id=result_next.response.transaction_id)

    summaries = run_billing_daily(
        target_date=billing_date,
        session=session,
    )

    assert summaries
    assert summaries[0].operations_count == 1
