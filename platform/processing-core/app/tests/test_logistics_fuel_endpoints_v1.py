import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

os.environ["DISABLE_CELERY"] = "1"

from app.models import fuel as fuel_models
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelStation, FuelTransaction, FuelTransactionStatus
from app.tests._logistics_route_harness import logistics_fuel_client_context


@pytest.fixture()
def logistics_client() -> Tuple[TestClient, sessionmaker]:
    with logistics_fuel_client_context() as ctx:
        yield ctx


def test_run_linker_and_fetch_trip_fuel(logistics_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = logistics_client
    with SessionLocal() as db:
        vehicle = FleetVehicle(tenant_id=1, client_id="client-1", plate_number="AA11", status=FleetVehicleStatus.ACTIVE)
        driver = FleetDriver(tenant_id=1, client_id="client-1", full_name="Driver", status=FleetDriverStatus.ACTIVE)
        network = FuelNetwork(name="N", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
        card = FuelCard(tenant_id=1, client_id="client-1", card_token="c1", status=FuelCardStatus.ACTIVE)
        db.add_all([vehicle, driver, network, card])
        db.commit()
        for item in [vehicle, driver, network, card]:
            db.refresh(item)

        station = FuelStation(network_id=str(network.id), station_code="S1", name="Station", country="RU", city="M", lat="55.75", lon="37.6", status=fuel_models.FuelStationStatus.ACTIVE)
        db.add(station)
        db.commit()
        db.refresh(station)

    create = client.post(
        "/api/v1/logistics/orders",
        json={"tenant_id": 1, "client_id": "client-1", "order_type": "TRIP", "vehicle_id": str(vehicle.id), "driver_id": str(driver.id), "planned_start_at": (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(), "planned_end_at": (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},
    )
    assert create.status_code == 200
    trip_id = create.json()["id"]

    with SessionLocal() as db:
        tx = FuelTransaction(
            tenant_id=1,
            client_id="client-1",
            card_id=str(card.id),
            vehicle_id=str(vehicle.id),
            driver_id=str(driver.id),
            station_id=str(station.id),
            network_id=str(network.id),
            occurred_at=datetime.now(timezone.utc),
            fuel_type=fuel_models.FuelType.DIESEL,
            volume_ml=20000,
            amount_total_minor=200,
            unit_price_minor=10,
            currency="RUB",
            status=FuelTransactionStatus.SETTLED,
        )
        db.add(tx)
        db.commit()

    date_from = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    date_to = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    run = client.post("/api/v1/logistics/fuel/linker:run", params={"date_from": date_from, "date_to": date_to})
    assert run.status_code == 200

    trip_fuel = client.get(f"/api/v1/logistics/trips/{trip_id}/fuel")
    assert trip_fuel.status_code == 200
    assert trip_fuel.json()["trip_id"] == trip_id

    alerts = client.get("/api/v1/logistics/fuel/alerts", params={"date_from": date_from, "date_to": date_to})
    assert alerts.status_code == 200
