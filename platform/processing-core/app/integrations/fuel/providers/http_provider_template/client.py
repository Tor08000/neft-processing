from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.integrations.fuel.base import (
    CardsPage,
    HealthResult,
    ProviderCard,
    ProviderResult,
    ProviderStatement,
    ProviderTransaction,
    TxPage,
)
from app.integrations.fuel.providers.http_provider_template import mapper
from app.integrations.fuel.registry import register


@register
class HttpProviderTemplateConnector:
    code = "http_provider_template"

    def health(self, conn) -> HealthResult:
        return HealthResult(status="ok", details={"provider": self.code})

    def list_cards(self, conn, cursor: str | None = None) -> CardsPage:
        cards = [ProviderCard(provider_card_id="card-001", status="ACTIVE")]
        return CardsPage(items=cards, next_cursor=None)

    def block_card(self, conn, provider_card_id: str, reason: str) -> ProviderResult:
        return ProviderResult(success=True, message=f"blocked:{provider_card_id}")

    def unblock_card(self, conn, provider_card_id: str, reason: str) -> ProviderResult:
        return ProviderResult(success=True, message=f"unblocked:{provider_card_id}")

    def fetch_transactions(
        self,
        conn,
        *,
        since: datetime,
        until: datetime,
        cursor: str | None = None,
    ) -> TxPage:
        payload = {
            "id": f"tx-{since.isoformat()}",
            "card_id": "card-001",
            "occurred_at": since.isoformat(),
            "amount": "1200.00",
            "currency": "RUB",
            "volume_liters": "42.1",
            "category": "fuel",
            "merchant": "Template Fuel",
            "station_id": "ST-009",
            "location": "St. Petersburg",
        }
        tx = ProviderTransaction(
            provider_tx_id=payload["id"],
            provider_card_id=payload["card_id"],
            occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            amount=Decimal(payload["amount"]),
            currency=payload["currency"],
            volume_liters=Decimal(payload["volume_liters"]),
            category=payload["category"],
            merchant_name=payload["merchant"],
            station_id=payload["station_id"],
            location=payload["location"],
            raw_payload=payload,
        )
        return TxPage(items=[tx], next_cursor=None)

    def fetch_statements(
        self,
        conn,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> ProviderStatement:
        payload = {
            "id": f"statement-{period_end.date().isoformat()}",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "currency": "RUB",
            "total_out": "1200.00",
        }
        return ProviderStatement(
            provider_statement_id=payload["id"],
            period_start=datetime.fromisoformat(payload["period_start"]),
            period_end=datetime.fromisoformat(payload["period_end"]),
            currency=payload["currency"],
            total_in=Decimal("0"),
            total_out=Decimal(payload["total_out"]),
            closing_balance=Decimal("-1200.00"),
            lines=[{"type": "fuel", "amount": payload["total_out"]}],
            raw_payload=payload,
        )

    def map_transaction(self, item: ProviderTransaction) -> dict:
        return mapper.map_transaction(provider_code=self.code, item=item)

    def map_statement(self, statement: ProviderStatement) -> dict:
        return mapper.map_statement(provider_code=self.code, statement=statement)

    def map_raw_event(self, payload: dict) -> dict:
        return mapper.map_raw_event(provider_code=self.code, payload=payload)
