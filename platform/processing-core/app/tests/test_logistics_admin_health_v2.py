import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app import models  # noqa: F401
from app.db import Base, get_db
from app.models.fuel import FuelCard, FuelNetwork, FuelStation, FuelTransaction, FuelTransactionStatus
from app.routers.admin.logistics import router as admin_logistics_router
from app.schemas.logistics import LogisticsStopIn
from app.services.logistics import repository, routes
from app.services.logistics.orders import create_order, start_order
from app.services.logistics.defaults import HEALTH_DEFAULTS


@pytest.fixture()
def admin_client() -> Tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(admin_logistics_router, prefix="/admin")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, SessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_fuel(db: Session) -> tuple[FuelCard, FuelStation]:
    network = FuelNetwork(name="Net", provider_code="NET-1", status=models.FuelNetworkStatus.ACTIVE)
    db.add(network)
    db.commit()
    db.refresh(network)
    station = FuelStation(
        network_id=str(network.id),
        station_network_id=None,
        station_code="ST-1",
        name="Station",
        country="RU",
        region="MSK",
        city="Moscow",
        lat="55.75",
        lon="37.6",
        status=models.FuelStationStatus.ACTIVE,
    )
    card = FuelCard(
        tenant_id=1,
        client_id="client-1",
        card_token="token-1",
        status=models.FuelCardStatus.ACTIVE,
    )
    db.add_all([station, card])
    db.commit()
    db.refresh(card)
    db.refresh(station)
    return card, station


def test_health_and_recompute_idempotent(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client
    with SessionLocal() as db:
        vehicle = models.FleetVehicle(
            tenant_id=1,
            client_id="client-1",
            plate_number="HEALTH1",
            status=models.FleetVehicleStatus.ACTIVE,
        )
        driver = models.FleetDriver(
            tenant_id=1,
            client_id="client-1",
            full_name="Health Driver",
            status=models.FleetDriverStatus.ACTIVE,
        )
        db.add_all([vehicle, driver])
        db.commit()
        db.refresh(vehicle)
        db.refresh(driver)

        order = create_order(
            db,
            tenant_id=1,
            client_id="client-1",
            order_type=models.LogisticsOrderType.DELIVERY,
            vehicle_id=str(vehicle.id),
            driver_id=str(driver.id),
        )
        start_order(db, order_id=str(order.id), started_at=datetime.now(timezone.utc) - timedelta(hours=1))

        route = routes.create_route(db, order_id=str(order.id), distance_km=10.0, planned_duration_minutes=30)
        routes.activate_route(db, route_id=str(route.id))
        routes.upsert_stops(
            db,
            route_id=str(route.id),
            stops=[
                LogisticsStopIn(
                    sequence=0,
                    stop_type=models.LogisticsStopType.FUEL,
                    name="Fuel Stop",
                    lat=55.75,
                    lon=37.6,
                    planned_arrival_at=datetime.now(timezone.utc),
                    status=models.LogisticsStopStatus.PENDING,
                )
            ],
        )

        card, station = _seed_fuel(db)
        tx = FuelTransaction(
            tenant_id=1,
            client_id="client-1",
            card_id=str(card.id),
            vehicle_id=str(vehicle.id),
            driver_id=str(driver.id),
            station_id=str(station.id),
            network_id=str(station.network_id),
            occurred_at=datetime.now(timezone.utc),
            fuel_type=models.FuelType.DIESEL,
            volume_ml=1000,
            unit_price_minor=50,
            amount_total_minor=50,
            currency="RUB",
            status=FuelTransactionStatus.SETTLED,
        )
        db.add(tx)
        db.commit()

    resp = client.get("/admin/logistics/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["stats"]["stale_tracking"] >= 1
    assert payload["stats"]["fuel_tx_without_link"] >= 1

    recompute = client.post(f"/admin/logistics/orders/{order.id}/recompute")
    assert recompute.status_code == 200
    recompute_again = client.post(f"/admin/logistics/orders/{order.id}/recompute")
    assert recompute_again.status_code == 200

    with SessionLocal() as db:
        links = repository.list_fuel_links(db, order_id=str(order.id))
        assert len(links) == 1
