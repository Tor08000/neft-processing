from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from app.integrations.fuel.normalize import (
    CanonicalStatement,
    CanonicalTransaction,
    normalize_category,
)
from app.integrations.fuel.registry import register


@register
class StubProviderConnector:
    code = "stub_provider"

    def health(self, conn) -> HealthResult:
        return HealthResult(status="ok", details={"provider": self.code})

    def list_cards(self, conn, cursor: str | None = None) -> CardsPage:
        return CardsPage(
            items=[ProviderCard(provider_card_id="stub-card-1", status="ACTIVE", card_alias="CARD-1")],
            next_cursor=None,
        )

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
        sample = ProviderTransaction(
            provider_tx_id=f"stub-{since.isoformat()}",
            provider_card_id="stub-card-1",
            occurred_at=since + timedelta(minutes=5),
            amount=Decimal("1500.25"),
            currency="RUB",
            volume_liters=Decimal("35.5"),
            category="fuel",
            merchant_name="Stub Fuel Station",
            station_id="ST-001",
            location="Moscow",
            raw_payload={"id": "stub-1", "amount": "1500.25", "category": "fuel"},
        )
        return TxPage(items=[sample], next_cursor=None)

    def fetch_statements(
        self,
        conn,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> ProviderStatement:
        return ProviderStatement(
            provider_statement_id=f"statement-{period_end.date().isoformat()}",
            period_start=period_start,
            period_end=period_end,
            currency="RUB",
            total_in=Decimal("0"),
            total_out=Decimal("1500.25"),
            closing_balance=Decimal("-1500.25"),
            lines=[{"type": "fuel", "amount": "1500.25"}],
            raw_payload={"statement": "stub"},
        )

    def map_transaction(self, item: ProviderTransaction) -> dict:
        normalized_category = normalize_category(item.category)
        return CanonicalTransaction(
            provider_code=self.code,
            provider_tx_id=item.provider_tx_id,
            provider_card_id=item.provider_card_id,
            card_alias=None,
            occurred_at=item.occurred_at,
            amount=item.amount,
            currency=item.currency,
            volume_liters=item.volume_liters,
            category=normalized_category.value,
            merchant_name=item.merchant_name,
            station_id=item.station_id,
            location=item.location,
            raw_payload=item.raw_payload,
        ).__dict__

    def map_statement(self, statement: ProviderStatement) -> dict:
        return CanonicalStatement(
            provider_code=self.code,
            provider_statement_id=statement.provider_statement_id,
            period_start=statement.period_start,
            period_end=statement.period_end,
            currency=statement.currency,
            total_in=statement.total_in,
            total_out=statement.total_out,
            closing_balance=statement.closing_balance,
            lines=statement.lines,
            raw_payload=statement.raw_payload,
        ).__dict__

    def map_raw_event(self, payload: dict) -> dict:
        now = datetime.now(timezone.utc)
        return CanonicalTransaction(
            provider_code=self.code,
            provider_tx_id=payload.get("id"),
            provider_card_id=payload.get("card_id"),
            card_alias=None,
            occurred_at=now,
            amount=Decimal(str(payload.get("amount", "0"))),
            currency=payload.get("currency", "RUB"),
            volume_liters=Decimal(str(payload.get("volume", "0"))) if payload.get("volume") else None,
            category=payload.get("category"),
            merchant_name=payload.get("merchant"),
            station_id=payload.get("station_id"),
            location=payload.get("location"),
            raw_payload=payload,
        ).__dict__
