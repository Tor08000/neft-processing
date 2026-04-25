from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sqlalchemy.orm import Session
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelFraudSignal,
    FuelFraudSignalType,
    FuelNetwork,
    FuelRiskProfile,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
    FuelTransactionStatus,
    FuelType,
)
from app.models.logistics import (
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsRoute,
    LogisticsRouteConstraint,
    LogisticsRouteStatus,
    LogisticsStop,
    LogisticsStopStatus,
    LogisticsStopType,
)
from app.models.risk_policy import RiskPolicy
from app.models.risk_score import RiskLevel
from app.models.risk_threshold import RiskThreshold
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskDecisionType, RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.schemas.fuel import DeclineCode, FuelAuthorizeRequest
from app.services.fuel.authorize import authorize_fuel_tx
from app.services.fuel.fraud import evaluate_fraud_signals
from app.services.fuel.risk_context import build_risk_context_for_fuel_tx
from app.tests._fuel_runtime_test_harness import FUEL_FRAUD_SIGNAL_TEST_TABLES, fuel_runtime_session_context


@pytest.fixture()
def session() -> Session:
    with fuel_runtime_session_context(tables=FUEL_FRAUD_SIGNAL_TEST_TABLES) as db:
        yield db


def _seed_core(db):
    vehicle = FleetVehicle(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        plate_number="A123BC",
        tank_capacity_liters=50,
        status=FleetVehicleStatus.ACTIVE,
    )
    driver = FleetDriver(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        full_name="Driver",
        status=FleetDriverStatus.ACTIVE,
    )
    network = FuelNetwork(id=str(uuid4()), name="NET-1", provider_code="net-1", status="ACTIVE")
    station = FuelStation(
        id=str(uuid4()),
        network_id=network.id,
        station_network_id=None,
        station_code="ST-1",
        name="Station",
        country="RU",
        region="MSK",
        city="Moscow",
        lat="55.0",
        lon="37.0",
        status=FuelStationStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-token",
        status=FuelCardStatus.ACTIVE,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
    )
    db.add_all([vehicle, driver, network, station, card])
    db.commit()
    return vehicle, driver, station, card


def _seed_order(db, vehicle_id: str, driver_id: str) -> LogisticsOrder:
    order = LogisticsOrder(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        order_type="DELIVERY",
        status=LogisticsOrderStatus.IN_PROGRESS,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
    )
    route = LogisticsRoute(
        id=str(uuid4()),
        order_id=order.id,
        version=1,
        status=LogisticsRouteStatus.ACTIVE,
    )
    constraint = LogisticsRouteConstraint(
        id=str(uuid4()),
        route_id=route.id,
        max_route_deviation_m=3000,
        max_stop_radius_m=100,
        allowed_fuel_window_minutes=120,
    )
    stop = LogisticsStop(
        id=str(uuid4()),
        route_id=route.id,
        sequence=1,
        stop_type=LogisticsStopType.FUEL,
        name="Fuel stop",
        lat=55.0,
        lon=37.0,
        planned_arrival_at=datetime.now(timezone.utc),
        status=LogisticsStopStatus.PENDING,
    )
    db.add_all([order, route, constraint, stop])
    db.commit()
    return order


def test_detects_fuel_off_route_strong(session):
    vehicle, driver, station, card = _seed_core(session)
    _seed_order(session, vehicle.id, driver.id)
    station.lat = "56.0"
    station.lon = "38.0"
    session.commit()

    signals = evaluate_fraud_signals(
        session,
        tenant_id=1,
        client_id="client-1",
        card=card,
        station=station,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        occurred_at=datetime.now(timezone.utc),
        volume_ml=10000,
        amount_minor=100000,
        request_vehicle_plate=None,
        request_driver_id=None,
        include_current=True,
    )
    assert any(signal.signal_type == FuelFraudSignalType.FUEL_OFF_ROUTE_STRONG for signal in signals)


def test_detects_station_burst(session):
    vehicle, driver, station, card = _seed_core(session)
    now = datetime.now(timezone.utc)
    for _ in range(4):
        new_card = FuelCard(
            id=str(uuid4()),
            tenant_id=1,
            client_id="client-1",
            card_token=str(uuid4()),
            status=FuelCardStatus.ACTIVE,
        )
        session.add(new_card)
        session.flush()
        session.add(
            FuelTransaction(
                tenant_id=1,
                client_id="client-1",
                card_id=new_card.id,
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                station_id=station.id,
                network_id=station.network_id,
                occurred_at=now - timedelta(minutes=5),
                fuel_type="DIESEL",
                volume_ml=60000,
                unit_price_minor=100,
                amount_total_minor=600000,
                currency="RUB",
                status=FuelTransactionStatus.AUTHORIZED,
            )
        )
    session.commit()

    signals = evaluate_fraud_signals(
        session,
        tenant_id=1,
        client_id="client-1",
        card=card,
        station=station,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        occurred_at=now,
        volume_ml=60000,
        amount_minor=600000,
        request_vehicle_plate=None,
        request_driver_id=None,
        include_current=True,
    )
    assert any(signal.signal_type == FuelFraudSignalType.MULTI_CARD_SAME_STATION_BURST for signal in signals)


def test_detects_repeated_night_refuel(session):
    vehicle, driver, station, card = _seed_core(session)
    # Keep the fixture robust even if SQLite returns naive datetimes during round-trips:
    # 23:30 UTC remains a "night" timestamp under both UTC-local and MSK-aware interpretation.
    night_time = datetime(2024, 1, 1, 23, 30, tzinfo=timezone.utc)
    for minute in (10, 20):
        session.add(
            FuelTransaction(
                tenant_id=1,
                client_id="client-1",
                card_id=card.id,
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                station_id=station.id,
                network_id=station.network_id,
                occurred_at=night_time - timedelta(minutes=minute),
                fuel_type="DIESEL",
                volume_ml=10000,
                unit_price_minor=100,
                amount_total_minor=100000,
                currency="RUB",
                status=FuelTransactionStatus.AUTHORIZED,
            )
        )
    session.commit()

    signals = evaluate_fraud_signals(
        session,
        tenant_id=1,
        client_id="client-1",
        card=card,
        station=station,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        occurred_at=night_time,
        volume_ml=10000,
        amount_minor=100000,
        request_vehicle_plate=None,
        request_driver_id=None,
        include_current=True,
    )
    assert any(signal.signal_type == FuelFraudSignalType.REPEATED_NIGHT_REFUEL for signal in signals)


def test_detects_tank_sanity_repeat(session):
    vehicle, driver, station, card = _seed_core(session)
    now = datetime.now(timezone.utc)
    session.add(
        FuelTransaction(
            tenant_id=1,
            client_id="client-1",
            card_id=card.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            station_id=station.id,
            network_id=station.network_id,
            occurred_at=now - timedelta(days=1),
            fuel_type="DIESEL",
            volume_ml=70000,
            unit_price_minor=100,
            amount_total_minor=700000,
            currency="RUB",
            status=FuelTransactionStatus.AUTHORIZED,
        )
    )
    session.commit()

    signals = evaluate_fraud_signals(
        session,
        tenant_id=1,
        client_id="client-1",
        card=card,
        station=station,
        vehicle_id=str(vehicle.id),
        driver_id=str(driver.id),
        occurred_at=now,
        volume_ml=70000,
        amount_minor=700000,
        request_vehicle_plate=None,
        request_driver_id=None,
        include_current=True,
    )
    assert any(signal.signal_type == FuelFraudSignalType.TANK_SANITY_REPEAT for signal in signals)


def test_risk_context_enriched_with_fraud_summary(session):
    vehicle, driver, station, card = _seed_core(session)
    session.add(
        FuelFraudSignal(
            tenant_id=1,
            client_id="client-1",
            signal_type=FuelFraudSignalType.FUEL_OFF_ROUTE_STRONG,
            severity=90,
            ts=datetime.now(timezone.utc),
            fuel_tx_id=None,
            order_id=None,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            station_id=station.id,
            network_id=station.network_id,
            explain={"note": "test"},
        )
    )
    session.commit()

    result = build_risk_context_for_fuel_tx(
        tenant_id=1,
        client_id="client-1",
        card=card,
        station=station,
        vehicle=vehicle,
        driver=driver,
        fuel_type=FuelType.DIESEL,
        amount_minor=1000,
        volume_ml=1000,
        occurred_at=datetime.now(timezone.utc),
        currency="RUB",
        subject_id="subject-1",
        policy_override_id=None,
        thresholds_override=None,
        policy_source="test",
        logistics_window_hours=None,
        severity_multiplier=None,
        db=session,
    )
    metadata = result.decision_context.metadata
    assert metadata["signals_last_24h_count"] >= 1
    assert metadata["has_strong_off_route"]


def test_strong_signal_blocks_under_enterprise_profile(session):
    vehicle, driver, station, card = _seed_core(session)
    _seed_order(session, vehicle.id, driver.id)
    station.lat = "56.0"
    station.lon = "38.0"
    session.commit()

    enterprise_policy_id = str(uuid4())

    session.add(
        RiskThresholdSet(
            id="fuel_default_v4",
            subject_type=RiskSubjectType.PAYMENT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.PAYMENT,
            block_threshold=95,
            review_threshold=70,
            allow_threshold=0,
        )
    )
    session.add_all(
        [
            RiskThreshold(
                threshold_set_id="fuel_default_v4",
                subject_type=RiskSubjectType.PAYMENT,
                min_score=0,
                max_score=94,
                risk_level=RiskLevel.LOW,
                outcome=RiskDecisionType.ALLOW,
                priority=1,
            ),
            RiskThreshold(
                threshold_set_id="fuel_default_v4",
                subject_type=RiskSubjectType.PAYMENT,
                min_score=95,
                max_score=100,
                risk_level=RiskLevel.VERY_HIGH,
                outcome=RiskDecisionType.BLOCK,
                priority=1,
            ),
        ]
    )
    session.add(
        RiskThresholdSet(
            id="enterprise_fuel_v4",
            subject_type=RiskSubjectType.PAYMENT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.PAYMENT,
            block_threshold=80,
            review_threshold=60,
            allow_threshold=0,
        )
    )
    session.add_all(
        [
            RiskThreshold(
                threshold_set_id="enterprise_fuel_v4",
                subject_type=RiskSubjectType.PAYMENT,
                min_score=0,
                max_score=79,
                risk_level=RiskLevel.LOW,
                outcome=RiskDecisionType.ALLOW,
                priority=1,
            ),
            RiskThreshold(
                threshold_set_id="enterprise_fuel_v4",
                subject_type=RiskSubjectType.PAYMENT,
                min_score=80,
                max_score=100,
                risk_level=RiskLevel.VERY_HIGH,
                outcome=RiskDecisionType.BLOCK,
                priority=1,
            ),
        ]
    )
    session.add(
        RiskPolicy(
            id=enterprise_policy_id,
            subject_type=RiskSubjectType.PAYMENT,
            threshold_set_id="enterprise_fuel_v4",
            model_selector="stub",
            priority=10,
            active=True,
        )
    )
    session.add(
        FuelRiskProfile(
            id=str(uuid4()),
            client_id="client-1",
            policy_id=enterprise_policy_id,
            thresholds_override=None,
            enabled=True,
        )
    )
    session.add(
        FuelFraudSignal(
            tenant_id=1,
            client_id="client-1",
            signal_type=FuelFraudSignalType.FUEL_OFF_ROUTE_STRONG,
            severity=90,
            ts=datetime.now(timezone.utc) - timedelta(minutes=10),
            fuel_tx_id=None,
            order_id=None,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            station_id=station.id,
            network_id=station.network_id,
            explain={"note": "pre-signal"},
        )
    )
    session.commit()

    payload = FuelAuthorizeRequest(
        card_token=card.card_token,
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=10.0,
        unit_price=100,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate=vehicle.plate_number,
    )
    result = authorize_fuel_tx(session, payload=payload)
    assert result.response.decline_code == DeclineCode.RISK_BLOCK


def test_regression_without_signals_allows(session):
    vehicle, driver, station, card = _seed_core(session)
    session.add(
        RiskThresholdSet(
            id="fuel_default_v4",
            subject_type=RiskSubjectType.PAYMENT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.PAYMENT,
            block_threshold=95,
            review_threshold=70,
            allow_threshold=0,
        )
    )
    session.add_all(
        [
            RiskThreshold(
                threshold_set_id="fuel_default_v4",
                subject_type=RiskSubjectType.PAYMENT,
                min_score=0,
                max_score=100,
                risk_level=RiskLevel.LOW,
                outcome=RiskDecisionType.ALLOW,
                priority=1,
            )
        ]
    )
    session.commit()

    payload = FuelAuthorizeRequest(
        card_token=card.card_token,
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=1.0,
        unit_price=100,
        currency="RUB",
        external_ref=str(uuid4()),
        vehicle_plate=vehicle.plate_number,
    )
    result = authorize_fuel_tx(session, payload=payload)
    assert result.response.decline_code is None
