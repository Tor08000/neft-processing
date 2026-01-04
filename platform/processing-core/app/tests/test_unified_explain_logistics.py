from datetime import datetime, timezone
from typing import Tuple
from uuid import uuid4

import pytest
from fastapi import FastAPI
from app.fastapi_utils import generate_unique_id
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db import Base, get_db
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
from app.models.logistics import (
    FuelRouteLink,
    LogisticsDeviationEvent,
    LogisticsDeviationEventType,
    LogisticsDeviationSeverity,
    LogisticsFuelRouteLinkType,
    LogisticsNavigatorExplain,
    LogisticsNavigatorExplainType,
    LogisticsOrder,
    LogisticsOrderStatus,
    LogisticsOrderType,
    LogisticsRiskSignal,
    LogisticsRiskSignalType,
    LogisticsRoute,
    LogisticsRouteSnapshot,
    LogisticsRouteStatus,
)
from app.routers.admin.explain import router as explain_router


@pytest.fixture()
def admin_client(admin_auth_headers: dict) -> Tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )

    Base.metadata.create_all(bind=engine)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(explain_router, prefix="/api/v1/admin")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        client.headers.update(admin_auth_headers)
        yield client, TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_fuel_refs(db: Session):
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
    card = FuelCard(
        id=str(uuid4()),
        tenant_id=1,
        client_id="client-1",
        card_token="card-1",
        status=FuelCardStatus.ACTIVE,
    )
    db.add_all([network, station, card])
    db.commit()
    return card, station, network


def test_unified_explain_logistics_sections(admin_client: Tuple[TestClient, sessionmaker]):
    client, SessionLocal = admin_client
    with SessionLocal() as db:
        card, station, network = _seed_fuel_refs(db)
        order = LogisticsOrder(
            tenant_id=1,
            client_id="client-1",
            order_type=LogisticsOrderType.DELIVERY,
            status=LogisticsOrderStatus.IN_PROGRESS,
            vehicle_id=None,
            driver_id=None,
            planned_start_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
        )
        db.add(order)
        db.flush()

        route = LogisticsRoute(
            order_id=order.id,
            version=1,
            status=LogisticsRouteStatus.ACTIVE,
            distance_km=120.5,
            planned_duration_minutes=90,
        )
        db.add(route)
        db.flush()

        snapshot = LogisticsRouteSnapshot(
            order_id=order.id,
            route_id=route.id,
            provider="navigator",
            geometry={"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            distance_km=120.5,
            eta_minutes=90,
        )
        db.add(snapshot)
        db.flush()

        explain = LogisticsNavigatorExplain(
            route_snapshot_id=snapshot.id,
            type=LogisticsNavigatorExplainType.DEVIATION,
            payload={"score": 0.82, "assumptions": ["gps"]},
        )
        db.add(explain)

        deviation = LogisticsDeviationEvent(
            order_id=order.id,
            route_id=route.id,
            event_type=LogisticsDeviationEventType.OFF_ROUTE,
            ts=datetime(2025, 1, 5, 12, 0, tzinfo=timezone.utc),
            severity=LogisticsDeviationSeverity.HIGH,
            distance_from_route_m=2000,
        )
        db.add(deviation)

        signal = LogisticsRiskSignal(
            tenant_id=1,
            client_id="client-1",
            order_id=order.id,
            vehicle_id=None,
            driver_id=None,
            signal_type=LogisticsRiskSignalType.ROUTE_DEVIATION_HIGH,
            severity=90,
            ts=datetime(2025, 1, 5, 12, 1, tzinfo=timezone.utc),
        )
        db.add(signal)

        tx = FuelTransaction(
            tenant_id=1,
            client_id="client-1",
            card_id=card.id,
            vehicle_id=None,
            driver_id=None,
            station_id=station.id,
            network_id=network.id,
            occurred_at=datetime(2025, 1, 5, 12, 5, tzinfo=timezone.utc),
            fuel_type="DIESEL",
            volume_ml=15000,
            unit_price_minor=500,
            amount_total_minor=7500,
            currency="RUB",
            status=FuelTransactionStatus.SETTLED,
        )
        db.add(tx)
        db.flush()

        link = FuelRouteLink(
            fuel_tx_id=tx.id,
            order_id=order.id,
            route_id=route.id,
            stop_id=None,
            link_type=LogisticsFuelRouteLinkType.AUTO_MATCH,
            distance_to_stop_m=500,
            time_delta_minutes=5,
        )
        db.add(link)
        db.commit()

    response = client.get(f"/api/v1/admin/explain?fuel_tx_id={tx.id}")
    assert response.status_code == 200
    payload = response.json()
    assert "logistics" in payload["sections"]
    assert "navigator" in payload["sections"]
    events = payload["sections"]["logistics"]["deviation_events"]
    assert any(event["event_type"] == "OFF_ROUTE" for event in events)