from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.integrations.fuel.base import ProviderTransaction
from app.integrations.fuel.providers.http_provider_template import mapper


def test_template_mapper_transaction() -> None:
    tx = ProviderTransaction(
        provider_tx_id="tx-1",
        provider_card_id="card-1",
        occurred_at=datetime(2024, 1, 1, 0, 0, 0),
        amount=Decimal("10.00"),
        currency="RUB",
        volume_liters=Decimal("5"),
        category="fuel",
        merchant_name="Template Fuel",
        station_id="ST-1",
        location="Moscow",
        raw_payload={"id": "tx-1"},
    )

    mapped = mapper.map_transaction(provider_code="http_provider_template", item=tx)

    assert mapped["provider_code"] == "http_provider_template"
    assert mapped["provider_tx_id"] == "tx-1"
    assert mapped["category"] == "FUEL"
