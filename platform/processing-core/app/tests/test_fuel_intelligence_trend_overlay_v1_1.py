from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.crm import CRMClient, CRMClientStatus
from app.models.fleet import FleetDriver, FleetDriverStatus, FleetVehicle, FleetVehicleStatus
from app.models.fleet_intelligence import (
    DriverBehaviorLevel,
    FIDriverScore,
    FITrendEntityType,
    FITrendLabel,
    FITrendMetric,
    FITrendSnapshot,
    FITrendWindow,
)
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetwork,
    FuelNetworkStatus,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
    FuelTransactionStatus,
)
from app.services.explain.unified import build_unified_explain
from app.tests._fleet_intelligence_test_harness import FLEET_INTELLIGENCE_EXPLAIN_TEST_TABLES
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture()
def db_session() -> Session:
    with scoped_session_context(tables=FLEET_INTELLIGENCE_EXPLAIN_TEST_TABLES) as session:
        yield session


def test_fuel_insights_include_trend_overlay(db_session: Session):
    db = db_session
    client = CRMClient(
        id="client-1",
        tenant_id=1,
        legal_name="Client",
        country="RU",
        timezone="Europe/Moscow",
        status=CRMClientStatus.ACTIVE,
    )
    driver = FleetDriver(
        tenant_id=1,
        client_id="client-1",
        full_name="Driver",
        status=FleetDriverStatus.ACTIVE,
    )
    vehicle = FleetVehicle(
        tenant_id=1,
        client_id="client-1",
        plate_number="VEH-1",
        status=FleetVehicleStatus.ACTIVE,
    )
    network = FuelNetwork(id=str(uuid4()), name="Net", provider_code="NET", status=FuelNetworkStatus.ACTIVE)
    station = FuelStation(
        network_id=network.id,
        station_network_id=None,
        station_code="ST-1",
        name="Station",
        country="RU",
        region="RU",
        city="SPB",
        lat="0",
        lon="0",
        status=FuelStationStatus.ACTIVE,
    )
    db.add_all([client, driver, vehicle, network, station])
    db.flush()
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-1",
        status=FuelCardStatus.ACTIVE,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
    )
    driver_score = FIDriverScore(
        tenant_id=1,
        client_id="client-1",
        driver_id=driver.id,
        computed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
        window_days=7,
        score=80,
        level=DriverBehaviorLevel.HIGH,
        explain={"top_factors": []},
    )
    tx = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=card.id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        station_id=station.id,
        network_id=network.id,
        occurred_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
        fuel_type="DIESEL",
        volume_ml=15000,
        unit_price_minor=500,
        amount_total_minor=7500,
        currency="RUB",
        status=FuelTransactionStatus.SETTLED,
        meta={
            "fraud_signals": [
                {"type": "DRIVER_VEHICLE_MISMATCH"},
                {"type": "STATION_OUTLIER_CLUSTER"},
            ]
        },
    )
    driver_trend = FITrendSnapshot(
        tenant_id=1,
        client_id="client-1",
        entity_type=FITrendEntityType.DRIVER,
        entity_id=str(driver.id),
        metric=FITrendMetric.DRIVER_BEHAVIOR_SCORE,
        window=FITrendWindow.D7,
        current_value=80.0,
        baseline_value=70.0,
        delta=10.0,
        delta_pct=14.3,
        label=FITrendLabel.DEGRADING,
        computed_day=datetime(2025, 1, 11, tzinfo=timezone.utc).date(),
        computed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
        explain={"top_factors": []},
    )
    station_trend = FITrendSnapshot(
        tenant_id=1,
        client_id="client-1",
        entity_type=FITrendEntityType.STATION,
        entity_id=str(station.id),
        metric=FITrendMetric.STATION_TRUST_SCORE,
        window=FITrendWindow.D30,
        current_value=40.0,
        baseline_value=40.0,
        delta=0.0,
        delta_pct=0.0,
        label=FITrendLabel.STABLE,
        computed_day=datetime(2025, 1, 11, tzinfo=timezone.utc).date(),
        computed_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
        explain={"reasons": []},
    )
    db.add_all([card, driver_score, tx, driver_trend, station_trend])
    db.commit()

    response = build_unified_explain(db, fuel_tx_id=str(tx.id))
    insights = response.sections["fleet_intelligence"]["fuel_insights"]
    insight_map = {item["code"]: item for item in insights}

    driver_insight = insight_map["DRIVER_FUEL_MISMATCH"]
    assert driver_insight["severity"] == "WARNING"
    assert driver_insight["trend_message"] == "Ухудшается последние 14 дней"
    assert driver_insight["trend_overlay"]["driver"]["label"] == FITrendLabel.DEGRADING.value
    assert "delta_7d" in driver_insight["trend_overlay"]["driver"]

    station_insight = insight_map["STATION_FUEL_SPIKE"]
    assert station_insight["severity"] == "INFO"
    assert station_insight["trend_message"] == "Стабильно"
    assert station_insight["trend_overlay"]["station"]["label"] == FITrendLabel.STABLE.value
