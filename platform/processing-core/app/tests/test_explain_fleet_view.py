from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelNetwork,
    FuelNetworkStatus,
    FuelStation,
    FuelStationStatus,
    FuelTransaction,
    FuelTransactionStatus,
    FuelType,
)
from app.models.logistics import (
    FuelRouteLink,
    LogisticsDeviationEvent,
    LogisticsDeviationEventType,
    LogisticsDeviationSeverity,
    LogisticsFuelRouteLinkType,
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsOrderType,
    LogisticsRoute,
    LogisticsRouteConstraint,
    LogisticsRouteSnapshot,
    LogisticsRouteStatus,
    LogisticsStop,
    LogisticsStopStatus,
    LogisticsStopType,
)
from app.schemas.admin.unified_explain import UnifiedExplainView
from app.services.explain.unified import build_unified_explain
from app.tests._explain_test_harness import EXPLAIN_UNIFIED_FUEL_TEST_TABLES
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture
def session():
    with scoped_session_context(tables=EXPLAIN_UNIFIED_FUEL_TEST_TABLES) as db:
        yield db


def test_fleet_views_include_recommendations(session):
    network = FuelNetwork(
        id=str(uuid4()),
        name="Network",
        provider_code="provider",
        status=FuelNetworkStatus.ACTIVE,
    )
    station = FuelStation(
        network_id=network.id,
        station_network_id=None,
        name="Station",
        status=FuelStationStatus.ACTIVE,
    )
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-1",
        status=FuelCardStatus.ACTIVE,
    )
    session.add_all([network, station, card])
    session.flush()

    fuel_tx = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=card.id,
        station_id=station.id,
        network_id=network.id,
        occurred_at=datetime(2025, 1, 10, 12, 32, tzinfo=timezone.utc),
        fuel_type=FuelType.DIESEL,
        volume_ml=1000,
        unit_price_minor=50,
        amount_total_minor=50000,
        currency="RUB",
        status=FuelTransactionStatus.DECLINED,
        meta={
            "fraud_signals": [
                {
                    "type": "FUEL_OFF_ROUTE_STRONG",
                    "severity": 90,
                }
            ]
        },
    )
    order = LogisticsOrder(
        tenant_id=1,
        client_id="client-1",
        order_type=LogisticsOrderType.DELIVERY,
        status=LogisticsOrderStatus.IN_PROGRESS,
    )
    session.add_all([fuel_tx, order])
    session.flush()

    route = LogisticsRoute(order_id=order.id, version=1, status=LogisticsRouteStatus.ACTIVE)
    session.add(route)
    session.flush()

    stop = LogisticsStop(
        route_id=route.id,
        sequence=1,
        stop_type=LogisticsStopType.FUEL,
        status=LogisticsStopStatus.PENDING,
        name="Fuel stop",
    )
    session.add(stop)
    session.flush()

    constraint = LogisticsRouteConstraint(
        route_id=route.id,
        max_route_deviation_m=5000,
        max_stop_radius_m=100,
        allowed_fuel_window_minutes=30,
    )
    snapshot = LogisticsRouteSnapshot(
        order_id=order.id,
        route_id=route.id,
        provider="provider",
        geometry={},
        distance_km=120.0,
        eta_minutes=180,
    )
    deviation = LogisticsDeviationEvent(
        order_id=order.id,
        route_id=route.id,
        event_type=LogisticsDeviationEventType.OFF_ROUTE,
        ts=datetime(2025, 1, 10, 12, 35, tzinfo=timezone.utc),
        distance_from_route_m=12400,
        stop_id=stop.id,
        severity=LogisticsDeviationSeverity.HIGH,
        explain={"signal_type": "OFF_ROUTE"},
    )
    link = FuelRouteLink(
        fuel_tx_id=fuel_tx.id,
        order_id=order.id,
        route_id=route.id,
        stop_id=stop.id,
        link_type=LogisticsFuelRouteLinkType.AUTO_MATCH,
        distance_to_stop_m=12400,
        time_delta_minutes=5,
    )
    session.add_all([constraint, snapshot, deviation, link])
    session.commit()

    payload = build_unified_explain(
        session,
        fuel_tx_id=str(fuel_tx.id),
        view=UnifiedExplainView.FLEET,
    )

    logistics_section = payload.sections["logistics"]
    where = logistics_section["where"]
    threshold = logistics_section["threshold"]

    assert where["stop"]["id"] == str(stop.id)
    assert where["stop"]["name"] == "Fuel stop"
    assert where["distance_km"] == pytest.approx(12.4)
    assert where["ts"] == deviation.ts.isoformat()
    assert threshold["max_deviation_km"] == pytest.approx(5.0)
    assert threshold["stop_radius_m"] == 100
    assert threshold["allowed_window_min"] == 30
    assert "Скорректировать маршрут" in payload.recommendations
