from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.fuel import (
    FuelCard,
    FuelCardGroup,
    FuelCardGroupStatus,
    FuelCardStatus,
    FuelLimit,
    FuelLimitPeriod,
    FuelLimitScopeType,
    FuelLimitType,
    FuelStationNetwork,
    FuelNetwork,
    FuelStation,
    FuelTransaction,
    FuelTransactionStatus,
    FuelType,
)
from app.schemas.fuel import DeclineCode
from app.services.fuel import limits
from app.tests._fuel_runtime_test_harness import fuel_runtime_session_context


@pytest.fixture
def session() -> Session:
    with fuel_runtime_session_context() as db:
        yield db


def _seed_refs(db):
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
        tank_capacity_liters=60,
        status=FleetVehicleStatus.ACTIVE,
    )
    driver = FleetDriver(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        full_name="Ivan Petrov",
        status=FleetDriverStatus.ACTIVE,
    )
    group = FuelCardGroup(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        name="Group 1",
        status=FuelCardGroupStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-token-1",
        status=FuelCardStatus.ACTIVE,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        card_group_id=group.id,
    )
    db.add_all([network, station_network, station, vehicle, driver, group, card])
    db.commit()
    return card, station


def test_amount_limit_by_card_declines(session):
    card, station = _seed_refs(session)
    session.add(
        FuelLimit(
            tenant_id=1,
            client_id="client-1",
            scope_type=FuelLimitScopeType.CARD,
            scope_id=str(card.id),
            limit_type=FuelLimitType.AMOUNT,
            period=FuelLimitPeriod.DAILY,
            value=1_000,
            currency="RUB",
            active=True,
        )
    )
    session.commit()

    decision = limits.check_limits(
        db=session,
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        card_group_id=str(card.card_group_id),
        vehicle_id=str(card.vehicle_id),
        driver_id=str(card.driver_id),
        at=datetime.now(timezone.utc),
        amount_minor=2_000,
        volume_ml=1_000,
        currency="RUB",
        fuel_type=FuelType.DIESEL,
        station_id=str(station.id),
        station_network_id=str(station.station_network_id),
    )

    assert decision.allowed is False
    assert decision.decline_code == DeclineCode.LIMIT_EXCEEDED_AMOUNT


def test_volume_limit_by_vehicle_declines(session):
    card, station = _seed_refs(session)
    session.add(
        FuelLimit(
            tenant_id=1,
            client_id="client-1",
            scope_type=FuelLimitScopeType.VEHICLE,
            scope_id=str(card.vehicle_id),
            limit_type=FuelLimitType.VOLUME,
            period=FuelLimitPeriod.DAILY,
            value=1000,
            currency="RUB",
            active=True,
        )
    )
    session.commit()

    decision = limits.check_limits(
        db=session,
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        card_group_id=str(card.card_group_id),
        vehicle_id=str(card.vehicle_id),
        driver_id=str(card.driver_id),
        at=datetime.now(timezone.utc),
        amount_minor=100,
        volume_ml=2_000,
        currency="RUB",
        fuel_type=FuelType.DIESEL,
        station_id=str(station.id),
        station_network_id=str(station.station_network_id),
    )

    assert decision.allowed is False
    assert decision.decline_code == DeclineCode.LIMIT_EXCEEDED_VOLUME


def test_count_limit_by_driver_declines(session):
    card, station = _seed_refs(session)
    session.add(
        FuelLimit(
            tenant_id=1,
            client_id="client-1",
            scope_type=FuelLimitScopeType.DRIVER,
            scope_id=str(card.driver_id),
            limit_type=FuelLimitType.COUNT,
            period=FuelLimitPeriod.DAILY,
            value=1,
            currency="RUB",
            active=True,
        )
    )
    session.add(
        FuelTransaction(
            tenant_id=1,
            client_id="client-1",
            card_id=card.id,
            vehicle_id=card.vehicle_id,
            driver_id=card.driver_id,
            station_id=station.id,
            network_id=station.network_id,
            occurred_at=datetime.now(timezone.utc),
            fuel_type=FuelType.DIESEL,
            volume_ml=1_000,
            unit_price_minor=100,
            amount_total_minor=100,
            currency="RUB",
            status=FuelTransactionStatus.AUTHORIZED,
            external_ref=str(uuid4()),
        )
    )
    session.commit()

    decision = limits.check_limits(
        db=session,
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        card_group_id=str(card.card_group_id),
        vehicle_id=str(card.vehicle_id),
        driver_id=str(card.driver_id),
        at=datetime.now(timezone.utc),
        amount_minor=100,
        volume_ml=1_000,
        currency="RUB",
        fuel_type=FuelType.DIESEL,
        station_id=str(station.id),
        station_network_id=str(station.station_network_id),
    )

    assert decision.allowed is False
    assert decision.decline_code == DeclineCode.LIMIT_EXCEEDED_COUNT


def test_limit_priority_prefers_card_scope(session):
    card, station = _seed_refs(session)
    session.add_all(
        [
            FuelLimit(
                tenant_id=1,
                client_id="client-1",
                scope_type=FuelLimitScopeType.CARD,
                scope_id=str(card.id),
                limit_type=FuelLimitType.AMOUNT,
                period=FuelLimitPeriod.DAILY,
                value=500,
                currency="RUB",
                priority=1,
                active=True,
            ),
            FuelLimit(
                tenant_id=1,
                client_id="client-1",
                scope_type=FuelLimitScopeType.CLIENT,
                scope_id=None,
                limit_type=FuelLimitType.AMOUNT,
                period=FuelLimitPeriod.DAILY,
                value=5_000,
                currency="RUB",
                priority=0,
                active=True,
            ),
        ]
    )
    session.commit()

    decision = limits.check_limits(
        db=session,
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        card_group_id=str(card.card_group_id),
        vehicle_id=str(card.vehicle_id),
        driver_id=str(card.driver_id),
        at=datetime.now(timezone.utc),
        amount_minor=600,
        volume_ml=1_000,
        currency="RUB",
        fuel_type=FuelType.DIESEL,
        station_id=str(station.id),
        station_network_id=str(station.station_network_id),
    )

    assert decision.allowed is False
    assert decision.explain.scope_type == FuelLimitScopeType.CARD


def test_limit_priority_prefers_station_specific(session):
    card, station = _seed_refs(session)
    session.add_all(
        [
            FuelLimit(
                tenant_id=1,
                client_id="client-1",
                scope_type=FuelLimitScopeType.CARD,
                scope_id=str(card.id),
                limit_type=FuelLimitType.AMOUNT,
                period=FuelLimitPeriod.DAILY,
                value=500,
                currency="RUB",
                fuel_type_code=FuelType.DIESEL,
                station_network_id=str(station.station_network_id),
                priority=10,
                active=True,
            ),
            FuelLimit(
                tenant_id=1,
                client_id="client-1",
                scope_type=FuelLimitScopeType.CARD,
                scope_id=str(card.id),
                limit_type=FuelLimitType.AMOUNT,
                period=FuelLimitPeriod.DAILY,
                value=300,
                currency="RUB",
                fuel_type_code=FuelType.DIESEL,
                station_id=str(station.id),
                priority=20,
                active=True,
            ),
        ]
    )
    session.commit()

    decision = limits.check_limits(
        db=session,
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        card_group_id=str(card.card_group_id),
        vehicle_id=str(card.vehicle_id),
        driver_id=str(card.driver_id),
        at=datetime.now(timezone.utc),
        amount_minor=400,
        volume_ml=1_000,
        currency="RUB",
        fuel_type=FuelType.DIESEL,
        station_id=str(station.id),
        station_network_id=str(station.station_network_id),
    )

    assert decision.allowed is False
    assert decision.explain.applied_limit_id is not None
    assert "station" in decision.explain.matched_on


def test_limit_time_window_cross_midnight(session):
    card, station = _seed_refs(session)
    session.add(
        FuelLimit(
            tenant_id=1,
            client_id="client-1",
            scope_type=FuelLimitScopeType.CARD,
            scope_id=str(card.id),
            limit_type=FuelLimitType.AMOUNT,
            period=FuelLimitPeriod.DAILY,
            value=5_000,
            currency="RUB",
            fuel_type_code=FuelType.DIESEL,
            station_id=str(station.id),
            time_window_start=datetime.strptime("23:00", "%H:%M").time(),
            time_window_end=datetime.strptime("06:00", "%H:%M").time(),
            timezone="Europe/Moscow",
            active=True,
        )
    )
    session.commit()

    decision = limits.check_limits(
        db=session,
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        card_group_id=str(card.card_group_id),
        vehicle_id=str(card.vehicle_id),
        driver_id=str(card.driver_id),
        at=datetime.now(timezone.utc).replace(hour=12),
        amount_minor=100,
        volume_ml=1_000,
        currency="RUB",
        fuel_type=FuelType.DIESEL,
        station_id=str(station.id),
        station_network_id=str(station.station_network_id),
    )

    assert decision.allowed is False
    assert decision.decline_code == DeclineCode.LIMIT_TIME_WINDOW


def test_limit_time_window_boundary_allows(session):
    card, station = _seed_refs(session)
    session.add(
        FuelLimit(
            tenant_id=1,
            client_id="client-1",
            scope_type=FuelLimitScopeType.CARD,
            scope_id=str(card.id),
            limit_type=FuelLimitType.COUNT,
            period=FuelLimitPeriod.DAILY,
            value=5,
            currency="RUB",
            station_network_id=str(station.station_network_id),
            time_window_start=datetime.strptime("23:00", "%H:%M").time(),
            time_window_end=datetime.strptime("06:00", "%H:%M").time(),
            timezone="Europe/Moscow",
            active=True,
        )
    )
    session.commit()

    at_boundary = datetime(2024, 1, 1, 20, 0, tzinfo=timezone.utc)
    decision = limits.check_limits(
        db=session,
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        card_group_id=str(card.card_group_id),
        vehicle_id=str(card.vehicle_id),
        driver_id=str(card.driver_id),
        at=at_boundary,
        amount_minor=100,
        volume_ml=1_000,
        currency="RUB",
        fuel_type=FuelType.DIESEL,
        station_id=str(station.id),
        station_network_id=str(station.station_network_id),
    )

    assert decision.allowed is True


def test_limit_window_missing_allows(session):
    card, station = _seed_refs(session)
    session.add(
        FuelLimit(
            tenant_id=1,
            client_id="client-1",
            scope_type=FuelLimitScopeType.CARD,
            scope_id=str(card.id),
            limit_type=FuelLimitType.COUNT,
            period=FuelLimitPeriod.DAILY,
            value=5,
            currency="RUB",
            station_id=str(station.id),
            active=True,
        )
    )
    session.commit()

    decision = limits.check_limits(
        db=session,
        tenant_id=1,
        client_id="client-1",
        card_id=str(card.id),
        card_group_id=str(card.card_group_id),
        vehicle_id=str(card.vehicle_id),
        driver_id=str(card.driver_id),
        at=datetime.now(timezone.utc),
        amount_minor=100,
        volume_ml=1_000,
        currency="RUB",
        fuel_type=FuelType.DIESEL,
        station_id=str(station.id),
        station_network_id=str(station.station_network_id),
    )

    assert decision.allowed is True
