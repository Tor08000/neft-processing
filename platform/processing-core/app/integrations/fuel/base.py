from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class HealthResult:
    status: str
    details: dict[str, str] | None = None


@dataclass(frozen=True)
class ProviderResult:
    success: bool
    message: str | None = None


@dataclass(frozen=True)
class ProviderCard:
    provider_card_id: str
    status: str
    card_alias: str | None = None
    meta: dict | None = None


@dataclass(frozen=True)
class ProviderTransaction:
    provider_tx_id: str | None
    provider_card_id: str | None
    occurred_at: datetime
    amount: Decimal
    currency: str
    volume_liters: Decimal | None = None
    category: str | None = None
    merchant_name: str | None = None
    station_id: str | None = None
    location: str | None = None
    raw_payload: dict | None = None


@dataclass(frozen=True)
class ProviderStatement:
    provider_statement_id: str | None
    period_start: datetime
    period_end: datetime
    currency: str
    total_in: Decimal | None = None
    total_out: Decimal | None = None
    closing_balance: Decimal | None = None
    lines: list[dict] | None = None
    raw_payload: dict | None = None


@dataclass(frozen=True)
class CardsPage:
    items: list[ProviderCard]
    next_cursor: str | None = None


@dataclass(frozen=True)
class TxPage:
    items: list[ProviderTransaction]
    next_cursor: str | None = None


class FuelProviderConnector(Protocol):
    code: str

    def health(self, conn) -> HealthResult: ...

    def list_cards(self, conn, cursor: str | None = None) -> CardsPage: ...

    def block_card(self, conn, provider_card_id: str, reason: str) -> ProviderResult: ...

    def unblock_card(self, conn, provider_card_id: str, reason: str) -> ProviderResult: ...

    def fetch_transactions(
        self,
        conn,
        *,
        since: datetime,
        until: datetime,
        cursor: str | None = None,
    ) -> TxPage: ...

    def fetch_statements(
        self,
        conn,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> ProviderStatement: ...

    def map_transaction(self, item: ProviderTransaction) -> dict: ...

    def map_statement(self, statement: ProviderStatement) -> dict: ...

    def map_raw_event(self, payload: dict) -> dict: ...
