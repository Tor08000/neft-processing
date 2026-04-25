from datetime import datetime, timezone
from typing import Tuple
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
from app.routers.admin.explain import router as explain_router
from app.tests._explain_test_harness import EXPLAIN_UNIFIED_FUEL_TEST_TABLES
from app.tests._scoped_router_harness import router_client_context, scoped_session_context


@pytest.fixture()
def admin_client(admin_auth_headers: dict) -> Tuple[TestClient, Session]:
    with scoped_session_context(tables=EXPLAIN_UNIFIED_FUEL_TEST_TABLES) as db:
        with router_client_context(router=explain_router, prefix="/api/v1/admin", db_session=db) as client:
            client.headers.update(admin_auth_headers)
            yield client, db


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


def test_unified_explain_snapshot_hash_deterministic(admin_client: Tuple[TestClient, Session]):
    client, db = admin_client
    card, station, network = _seed_fuel_refs(db)
    tx = FuelTransaction(
        tenant_id=1,
        client_id="client-1",
        card_id=card.id,
        vehicle_id=None,
        driver_id=None,
        station_id=station.id,
        network_id=network.id,
        occurred_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
        fuel_type="DIESEL",
        volume_ml=15000,
        unit_price_minor=500,
        amount_total_minor=7500,
        currency="RUB",
        status=FuelTransactionStatus.AUTHORIZED,
    )
    db.add(tx)
    db.commit()

    first = client.get(f"/api/v1/admin/explain?fuel_tx_id={tx.id}&snapshot=true").json()
    second = client.get(f"/api/v1/admin/explain?fuel_tx_id={tx.id}&snapshot=true").json()
    assert first["ids"]["snapshot_hash"] == second["ids"]["snapshot_hash"]
