from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.fleet import FleetVehicle, FleetVehicleStatus
from app.models.fuel import FuelCard, FuelCardStatus, FuelLimit, FuelLimitPeriod, FuelLimitScopeType, FuelLimitType
from app.models.fuel import FuelNetwork, FuelStation, FuelStationNetwork
from app.models.rule import Rule
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.schemas.fuel import DeclineCode, FuelAuthorizeRequest
from app.services.fuel.authorize import authorize_fuel_tx
from app.tests._fuel_runtime_test_harness import fuel_runtime_session_context


@pytest.fixture
def session() -> Session:
    with fuel_runtime_session_context() as db:
        yield db


def _ensure_threshold_set(db: Session) -> None:
    if db.get(RiskThresholdSet, "fuel-authorize-thresholds"):
        return
    db.add(
        RiskThresholdSet(
            id="fuel-authorize-thresholds",
            subject_type=RiskSubjectType.PAYMENT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.PAYMENT,
            block_threshold=90,
            review_threshold=70,
            allow_threshold=0,
        )
    )
    db.commit()


def _seed_refs(db):
    _ensure_threshold_set(db)
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
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-token-1",
        status=FuelCardStatus.ACTIVE,
        vehicle_id=vehicle.id,
    )
    db.add_all([network, station_network, station, vehicle, card])
    db.commit()
    return card


def _authorize(db, *, volume_liters: float, external_ref: str | None = None) -> DeclineCode | None:
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=volume_liters,
        unit_price=100,
        currency="RUB",
        external_ref=external_ref or str(uuid4()),
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
    assert decline_code == DeclineCode.RISK_BLOCK


def test_authorize_idempotent_response(session):
    _seed_refs(session)
    external_ref = str(uuid4())
    payload = FuelAuthorizeRequest(
        card_token="card-token-1",
        network_code="net-1",
        station_code="ST-1",
        occurred_at=datetime.now(timezone.utc),
        fuel_type="DIESEL",
        volume_liters=1.0,
        unit_price=100,
        currency="RUB",
        external_ref=external_ref,
        vehicle_plate="A123BC",
    )
    first = authorize_fuel_tx(session, payload=payload).response
    second = authorize_fuel_tx(session, payload=payload).response
    assert first.status == second.status
    assert first.transaction_id == second.transaction_id


def test_station_risk_red_rule_soft_declines_and_sets_manual_review_flag(session):
    _seed_refs(session)
    station = session.query(FuelStation).filter(FuelStation.station_code == "ST-1").one()
    station.risk_zone = "RED"
    session.commit()

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
    assert result.response.status == "REVIEW"
    tx = result.transaction
    assert tx is not None
    assert tx.meta["decision"]["flags"]["manual_review_required"] is True
    assert "STATION_RISK_RED" in tx.meta["decision"]["reason_codes"]


def test_station_risk_red_rule_can_be_disabled(session):
    _seed_refs(session)
    station = session.query(FuelStation).filter(FuelStation.station_code == "ST-1").one()
    station.risk_zone = "RED"
    session.commit()

    authorize_fuel_tx(
        session,
        payload=FuelAuthorizeRequest(
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
        ),
    )
    rule = session.query(Rule).filter(Rule.name == "default_station_risk_red_soft_decline").one()
    rule.enabled = False
    session.commit()

    second = authorize_fuel_tx(
        session,
        payload=FuelAuthorizeRequest(
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
        ),
    )
    assert second.response.status == "ALLOW"
