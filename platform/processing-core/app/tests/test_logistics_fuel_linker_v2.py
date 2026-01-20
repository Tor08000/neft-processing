import os
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DISABLE_CELERY"] = "1"

from app.db import Base
from app.models import fleet as fleet_models
from app.models import fuel as fuel_models
from app.models import logistics as logistics_models
from app.models.fuel import FuelCard, FuelCardStatus, FuelNetwork, FuelStation, FuelTransaction, FuelTransactionStatus
from app.schemas.logistics import LogisticsStopIn
from app.services.logistics.defaults import FUEL_LINK_DEFAULTS
from app.services.logistics import fuel_linker, repository, routes
from app.services.logistics.orders import create_order


@pytest.fixture()
def db_session() -> Tuple[Session, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session, SessionLocal
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed_fuel(db: Session) -> tuple[FuelCard, FuelStation]:
    network = FuelNetwork(name="Network", provider_code="NET", status=fuel_models.FuelNetworkStatus.ACTIVE)
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
        status=fuel_models.FuelStationStatus.ACTIVE,
    )
    db.add(station)

    card = FuelCard(
        tenant_id=1,
        client_id="client-1",
        card_token="token-1",
        status=FuelCardStatus.ACTIVE,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    db.refresh(station)
    return card, station


def test_fuel_auto_link_and_off_route_signal(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    vehicle = fleet_models.FleetVehicle(
        tenant_id=1,
        client_id="client-1",
        plate_number="FUEL123",
        status=fleet_models.FleetVehicleStatus.ACTIVE,
    )
    driver = fleet_models.FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Fuel Driver",
        status=fleet_models.FleetDriverStatus.ACTIVE,
    )
    db.add_all([vehicle, driver])
    db.commit()
    db.refresh(vehicle)
    db.refresh(driver)

    card, station = _seed_fuel(db)

    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=logistics_models.LogisticsOrderType.DELIVERY,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
    )
    route = routes.create_route(db, order_id=str(order.id), distance_km=10.0, planned_duration_minutes=30)
    routes.activate_route(db, route_id=str(route.id))

    planned_arrival = datetime.now(timezone.utc) + timedelta(minutes=30)
    routes.upsert_stops(
        db,
        route_id=str(route.id),
        stops=[
            LogisticsStopIn(
                sequence=0,
                stop_type=logistics_models.LogisticsStopType.FUEL,
                name="Fuel Stop",
                lat=55.75,
                lon=37.6,
                planned_arrival_at=planned_arrival,
                status=logistics_models.LogisticsStopStatus.PENDING,
            )
        ],
    )

    tx = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        station_id=str(station.id),
        network_id=str(station.network_id),
        occurred_at=planned_arrival + timedelta(minutes=FUEL_LINK_DEFAULTS.allowed_fuel_window_minutes - 1),
        fuel_type=fuel_models.FuelType.DIESEL,
        volume_ml=1000,
        unit_price_minor=50,
        amount_total_minor=50,
        currency="RUB",
        status=FuelTransactionStatus.SETTLED,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    result = fuel_linker.auto_link_fuel_tx(db, transaction=tx)
    assert result.link is not None
    links = repository.list_fuel_links(db, order_id=str(order.id))
    assert links[0].stop_id is not None

    far_station = FuelStation(
        network_id=str(station.network_id),
        station_network_id=None,
        station_code="ST-2",
        name="Station Far",
        country="RU",
        region="SPB",
        city="SPB",
        lat=str(55.75 + 0.020),
        lon="37.6",
        status=fuel_models.FuelStationStatus.ACTIVE,
    )
    db.add(far_station)
    db.commit()
    db.refresh(far_station)

    tx_far = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        station_id=str(far_station.id),
        network_id=str(far_station.network_id),
        occurred_at=planned_arrival + timedelta(minutes=FUEL_LINK_DEFAULTS.allowed_fuel_window_minutes + 1),
        fuel_type=fuel_models.FuelType.DIESEL,
        volume_ml=1000,
        unit_price_minor=50,
        amount_total_minor=50,
        currency="RUB",
        status=FuelTransactionStatus.SETTLED,
    )
    db.add(tx_far)
    db.commit()
    db.refresh(tx_far)

    result_far = fuel_linker.auto_link_fuel_tx(db, transaction=tx_far)
    assert result_far.signal is not None
    signals = repository.list_risk_signals(db, order_id=str(order.id))
    assert any(signal.signal_type.value == "FUEL_OFF_ROUTE" for signal in signals)


def test_fuel_distance_thresholds(db_session: Tuple[Session, sessionmaker]):
    db, _ = db_session
    vehicle = fleet_models.FleetVehicle(
        tenant_id=1,
        client_id="client-1",
        plate_number="FUEL124",
        status=fleet_models.FleetVehicleStatus.ACTIVE,
    )
    driver = fleet_models.FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Fuel Driver 2",
        status=fleet_models.FleetDriverStatus.ACTIVE,
    )
    db.add_all([vehicle, driver])
    db.commit()
    db.refresh(vehicle)
    db.refresh(driver)

    card, station = _seed_fuel(db)
    order = create_order(
        db,
        tenant_id=1,
        client_id="client-1",
        order_type=logistics_models.LogisticsOrderType.DELIVERY,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
    )
    route = routes.create_route(db, order_id=str(order.id), distance_km=10.0, planned_duration_minutes=30)
    routes.activate_route(db, route_id=str(route.id))
    planned_arrival = datetime.now(timezone.utc)
    routes.upsert_stops(
        db,
        route_id=str(route.id),
        stops=[
            LogisticsStopIn(
                sequence=0,
                stop_type=logistics_models.LogisticsStopType.FUEL,
                name="Fuel Stop",
                lat=55.75,
                lon=37.6,
                planned_arrival_at=planned_arrival,
                status=logistics_models.LogisticsStopStatus.PENDING,
            )
        ],
    )

    near_station = FuelStation(
        network_id=str(station.network_id),
        station_network_id=None,
        station_code="ST-3",
        name="Station Near",
        country="RU",
        region="MSK",
        city="Moscow",
        lat=str(55.75 + 0.0045),
        lon="37.6",
        status=fuel_models.FuelStationStatus.ACTIVE,
    )
    mid_station = FuelStation(
        network_id=str(station.network_id),
        station_network_id=None,
        station_code="ST-4",
        name="Station Mid",
        country="RU",
        region="MSK",
        city="Moscow",
        lat=str(55.75 + 0.0065),
        lon="37.6",
        status=fuel_models.FuelStationStatus.ACTIVE,
    )
    db.add_all([near_station, mid_station])
    db.commit()
    db.refresh(near_station)
    db.refresh(mid_station)

    tx_near = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        station_id=str(near_station.id),
        network_id=str(near_station.network_id),
        occurred_at=planned_arrival,
        fuel_type=fuel_models.FuelType.DIESEL,
        volume_ml=1000,
        unit_price_minor=50,
        amount_total_minor=50,
        currency="RUB",
        status=FuelTransactionStatus.SETTLED,
    )
    db.add(tx_near)
    db.commit()
    db.refresh(tx_near)
    result_near = fuel_linker.auto_link_fuel_tx(db, transaction=tx_near)
    assert result_near.link is not None
    assert result_near.signal is None

    tx_mid = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        station_id=str(mid_station.id),
        network_id=str(mid_station.network_id),
        occurred_at=planned_arrival,
        fuel_type=fuel_models.FuelType.DIESEL,
        volume_ml=1000,
        unit_price_minor=50,
        amount_total_minor=50,
        currency="RUB",
        status=FuelTransactionStatus.SETTLED,
    )
    db.add(tx_mid)
    db.commit()
    db.refresh(tx_mid)
    result_mid = fuel_linker.auto_link_fuel_tx(db, transaction=tx_mid)
    assert result_mid.link is not None
    assert result_mid.signal is not None
