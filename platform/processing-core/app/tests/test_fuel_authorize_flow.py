from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.db import Base, SessionLocal, engine
from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelLimit, FuelLimitPeriod, FuelLimitScopeType, FuelLimitType
from app.models.fuel import FuelNetwork, FuelStation
from app.schemas.fuel import DeclineCode, FuelAuthorizeRequest
from app.services.fuel.authorize import authorize_fuel_tx


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
    return card


def _authorize(db, *, volume_liters: float) -> DeclineCode | None:
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=volume_liters,
        unit_price=100,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate="A123BC",
    )
    result = authorize_fuel_tx(db, payload=payload)
    return result.response.decline_code


def test_authorize_allow_path(session):
    _seed_refs(session)
    decline_code = _authorize(session, volume_liters=1.0)
    assert decline_code is None


def test_authorize_decline_by_limit(session):
    _seed_refs(session)
    session.add(
        FuelLimit(
            tenant_id=1,
            client_id="client-1",
            scope_type=FuelLimitScopeType.CLIENT,
            scope_id=None,
            limit_type=FuelLimitType.AMOUNT,
            period=FuelLimitPeriod.DAILY,
            value=50,
            currency="RUB",
            active=True,
        )
    )
    session.commit()

    decline_code = _authorize(session, volume_liters=1.0)
    assert decline_code == DeclineCode.LIMIT_EXCEEDED_AMOUNT


def test_authorize_decline_by_risk(session):
    _seed_refs(session)
    decline_code = _authorize(session, volume_liters=100.0)
    assert decline_code == DeclineCode.TANK_SANITY_EXCEEDED
