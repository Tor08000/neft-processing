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
from app.schemas.admin.unified_explain import UnifiedExplainView
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


def test_accountant_view_from_limit_explain(session):
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
        decline_code="LIMIT_EXCEEDED_AMOUNT",
        meta={
            "limit_explain": {
                "scope_type": "CLIENT",
                "scope_id": "client-1",
                "period": "DAILY",
                "limit": 50000,
                "used": 50000,
                "remaining": 0,
                "time_window_start": "2025-01-01",
                "time_window_end": "2025-01-31",
            }
        },
    )
    session.add(fuel_tx)
    session.commit()

    payload = build_unified_explain(session, fuel_tx_id=str(fuel_tx.id), view=UnifiedExplainView.ACCOUNTANT)
    limits_section = payload.sections["limits"]
    limit_summary = limits_section["limit"]

    assert limit_summary["name"] is None
    assert limit_summary["scope"] == {"type": "CLIENT", "id": "client-1"}
    assert limit_summary["period"] == "DAILY"
    assert limit_summary["used"] == 50000
    assert limit_summary["remaining"] == 0
    assert limits_section["limit_value"] == 50000
    assert "Запросить повышение лимита" in payload.recommendations
