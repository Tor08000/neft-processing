from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
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
    LogisticsDeviationEvent,
    LogisticsDeviationEventType,
    LogisticsDeviationSeverity,
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsOrderType,
    LogisticsRoute,
    LogisticsRouteConstraint,
    LogisticsRouteSnapshot,
    LogisticsRouteStatus,
    LogisticsFuelRouteLinkType,
    FuelRouteLink,
    LogisticsStop,
    LogisticsStopStatus,
    LogisticsStopType,
)
from app.services.explain.unified import build_unified_explain


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_fleet_views_include_recommendations(session):
    network = FuelNetwork(name="Network", provider_code="provider", status=FuelNetworkStatus.ACTIVE)
    station = FuelStation(network_id=network.id, name="Station", status=FuelStationStatus.ACTIVE)
    card = FuelCard(tenant_id=1, client_id="client-1", card_token="card-1", status=FuelCardStatus.ACTIVE)
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
        route_snapshot_id=str(snapshot.id),
    )

    fuel_view = payload["sources"]["fuel"]["fleet_view"]
    assert fuel_view["where"]["stop_id"] == str(stop.id)
    assert fuel_view["where"]["distance_km"] == pytest.approx(12.4)
    assert fuel_view["threshold"]["max_deviation_km"] == pytest.approx(5.0)
    assert "Заправка произведена вне маршрута" in fuel_view["recommendations"]

    logistics_view = payload["sources"]["logistics"]["fleet_view"]
    assert logistics_view["where"]["stop_id"] == str(stop.id)
    assert logistics_view["where"]["distance_km"] == pytest.approx(12.4)
    assert logistics_view["threshold"]["max_deviation_km"] == pytest.approx(5.0)
    assert "Маршрут отклонён более чем на 12 км" in logistics_view["recommendations"]
