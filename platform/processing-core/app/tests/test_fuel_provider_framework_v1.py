from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.integrations.fuel.base import ProviderTransaction
from app.integrations.fuel.registry import get_connector, list_providers, load_default_providers


def test_registry_loads_default_providers() -> None:
    load_default_providers()
    providers = list(list_providers())
    assert "stub_provider" in providers
    assert "http_provider_template" in providers
    assert "virtual_fuel_network" in providers


def test_stub_provider_maps_transaction() -> None:
    load_default_providers()
    connector = get_connector("stub_provider")
    provider_tx = ProviderTransaction(
        provider_tx_id="tx-1",
        provider_card_id="card-1",
        occurred_at=datetime(2024, 1, 1, 0, 0, 0),
        amount=Decimal("10"),
        currency="RUB",
        volume_liters=Decimal("5"),
        category="fuel",
        merchant_name="Stub Fuel",
        station_id="ST-1",
        location="Moscow",
        raw_payload={"id": "tx-1"},
    )
    mapped = connector.map_transaction(provider_tx)

    assert mapped["provider_code"] == "stub_provider"
    assert mapped["provider_tx_id"] == "tx-1"
