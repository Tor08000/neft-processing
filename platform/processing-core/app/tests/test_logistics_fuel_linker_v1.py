import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

os.environ["DISABLE_CELERY"] = "1"

from app.models import fuel as fuel_models
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelStation, FuelTransaction, FuelTransactionStatus
from app.models.logistics import LogisticsOrderType
from app.services.logistics.fuel_linker_service import _candidate_for_tx
from app.services.logistics.orders import create_order
from app.tests._logistics_route_harness import logistics_fuel_session_context


@pytest.fixture()
def db() -> Session:
    with logistics_fuel_session_context() as ctx:
        session, _ = ctx
        yield session


def test_candidate_scoring_time_window_and_station(db: Session):
    vehicle = FleetVehicle(tenant_id=1, client_id="client-1", plate_number="X1", status=FleetVehicleStatus.ACTIVE)
    driver = FleetDriver(tenant_id=1, client_id="client-1", full_name="Driver", status=FleetDriverStatus.ACTIVE)
    network = FuelNetwork(name="N", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
    card = FuelCard(tenant_id=1, client_id="client-1", card_token="c1", status=FuelCardStatus.ACTIVE)
    db.add_all([vehicle, driver, network, card])
    db.commit()
    for model in [vehicle, driver, network, card]:
        db.refresh(model)

    station = FuelStation(
        network_id=str(network.id),
        station_code="S1",
        name="Station",
        country="RU",
        city="M",
        lat="55.75",
        lon="37.6",
        status=fuel_models.FuelStationStatus.ACTIVE,
    )
    db.add(station)
    db.commit()
    db.refresh(station)

    now = datetime.now(timezone.utc)
    trip = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=LogisticsOrderType.TRIP,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        planned_start_at=now - timedelta(hours=1),
        planned_end_at=now + timedelta(hours=1),
    )

    tx = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        station_id=str(station.id),
        network_id=str(network.id),
        occurred_at=now,
        fuel_type=fuel_models.FuelType.DIESEL,
        volume_ml=10000,
        amount_total_minor=100,
        unit_price_minor=10,
        currency="RUB",
        status=FuelTransactionStatus.SETTLED,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    candidate = _candidate_for_tx(db, tx, trip)
    assert candidate is not None
    assert candidate.score >= 40
