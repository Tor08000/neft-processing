from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetwork,
    FuelRiskShadowEvent,
    FuelStation,
    FuelStationNetwork,
)
from app.schemas.fuel import DeclineCode, FuelAuthorizeRequest
from app.services.fuel.authorize import authorize_fuel_tx
from app.tests._fuel_runtime_test_harness import FUEL_FRAUD_SIGNAL_TEST_TABLES, fuel_runtime_session_context


@pytest.fixture
def session():
    with fuel_runtime_session_context(tables=FUEL_FRAUD_SIGNAL_TEST_TABLES) as db:
        yield db


def _seed_refs(db, *, card_status: FuelCardStatus = FuelCardStatus.ACTIVE, tank_capacity_liters: int = 60):
    network = FuelNetwork(id=str(uuid4()), name="NET-1", provider_code="net-1", status="ACTIVE")
    station_network = FuelStationNetwork(id=str(uuid4()), name="Main Network", meta={"brand": "Main"})
    station = FuelStation(
        id=str(uuid4()),
        network_id=network.id,
        station_network_id=station_network.id,
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
        tank_capacity_liters=tank_capacity_liters,
        status=FleetVehicleStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-token-1",
        status=card_status,
        vehicle_id=vehicle.id,
    )
    db.add_all([network, station_network, station, vehicle, card])
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


def test_tank_sanity_declines(session):
    _seed_refs(session, tank_capacity_liters=60)
    decline_code = _authorize(session, volume_liters=100.0)
    assert decline_code == DeclineCode.RISK_BLOCK


def test_velocity_spike_declines(session):
    _seed_refs(session)
    for _ in range(5):
        _authorize(session, volume_liters=1.0)
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=1.0,
        unit_price=100,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate="A123BC",
    )
    result = authorize_fuel_tx(session, payload=payload)
    assert result.response.decline_code == DeclineCode.RISK_BLOCK


def test_blocked_card_declines(session):
    _seed_refs(session, card_status=FuelCardStatus.BLOCKED)
    decline_code = _authorize(session, volume_liters=1.0)
    assert decline_code == DeclineCode.CARD_BLOCKED


def test_shadow_risk_event_logged(session):
    _seed_refs(session)
    _authorize(session, volume_liters=1.0)
    assert session.query(FuelRiskShadowEvent).count() == 1
