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
                "period": "DAILY",
                "limit": 50000,
                "time_window_start": "2025-01-01",
                "time_window_end": "2025-01-31",
            }
        },
    )
    session.add(fuel_tx)
    session.commit()

    payload = build_unified_explain(session, fuel_tx_id=str(fuel_tx.id))
    accountant_view = payload["accountant_view"]

    assert accountant_view["limit"] == {
        "type": "DAILY",
        "value": 50000,
        "currency": "RUB",
    }
    assert accountant_view["period"] == "2025-01-01 → 2025-01-31"
    assert accountant_view["reason"] == "Превышение лимита"
    assert "Проверьте лимит клиента на период" in accountant_view["recommendations"]
    assert "Транзакция превышает дневной лимит" in accountant_view["recommendations"]
