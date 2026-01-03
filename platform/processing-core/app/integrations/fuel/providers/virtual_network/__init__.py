from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import random
import time
from typing import Any

from app.integrations.fuel.base import (
    CardsPage,
    HealthResult,
    ProviderCard,
    ProviderResult,
    ProviderStatement,
    ProviderTransaction,
    TxPage,
)
from app.integrations.fuel.normalize import CanonicalStatement, CanonicalTransaction, normalize_category
from app.integrations.fuel.providers.virtual_network.store import VirtualNetworkStore
from app.integrations.fuel.registry import register


@dataclass(frozen=True)
class _DelayProfile:
    min_ms: int
    max_ms: int
    timeout_rate: float

    def sleep(self, rng: random.Random) -> None:
        if self.max_ms <= 0:
            return
        delay = rng.randint(self.min_ms, self.max_ms)
        time.sleep(delay / 1000)

    def should_timeout(self, rng: random.Random) -> bool:
        if self.timeout_rate <= 0:
            return False
        return rng.random() < self.timeout_rate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


@register
class VirtualFuelNetworkConnector:
    code = "virtual_fuel_network"

    def __init__(self) -> None:
        self.store = VirtualNetworkStore()

    def _config(self) -> dict[str, Any]:
        return self.store.load_config()

    def _rng(self, seed: int | None = None) -> random.Random:
        config = self._config()
        actual_seed = seed if seed is not None else int(config.get("seed") or 7)
        return random.Random(actual_seed)

    def _delay_profile(self) -> _DelayProfile:
        config = self._config()
        delays = config.get("delays") or {}
        min_ms = int(delays.get("min_ms", 0))
        max_ms = int(delays.get("max_ms", min_ms))
        timeout_rate = float(delays.get("timeout_rate", 0))
        return _DelayProfile(min_ms=min_ms, max_ms=max_ms, timeout_rate=timeout_rate)

    def health(self, conn) -> HealthResult:
        config = self._config()
        return HealthResult(
            status="ok",
            details={"provider": self.code, "stations": str(len(config.get("stations") or []))},
        )

    def list_cards(self, conn, cursor: str | None = None) -> CardsPage:
        config = self._config()
        cards = config.get("cards") or []
        items = [
            ProviderCard(
                provider_card_id=card.get("provider_card_id") or card.get("card_alias") or "virtual-card",
                status=card.get("status", "ACTIVE"),
                card_alias=card.get("card_alias"),
                meta=card,
            )
            for card in cards
        ]
        return CardsPage(items=items, next_cursor=None)

    def block_card(self, conn, provider_card_id: str, reason: str) -> ProviderResult:
        state = self.store.update_state({"blocked_cards": {provider_card_id: {"reason": reason, "at": _now().isoformat()}}})
        blocked = state.get("blocked_cards", {})
        return ProviderResult(success=provider_card_id in blocked, message=reason)

    def unblock_card(self, conn, provider_card_id: str, reason: str) -> ProviderResult:
        state = self.store.load_config()
        blocked = dict(state.get("blocked_cards") or {})
        if provider_card_id in blocked:
            blocked.pop(provider_card_id)
            self.store.update_state({"blocked_cards": blocked})
        return ProviderResult(success=True, message=reason)

    def fetch_transactions(
        self,
        conn,
        *,
        since: datetime,
        until: datetime,
        cursor: str | None = None,
    ) -> TxPage:
        rng = self._rng(int(since.timestamp()))
        delay = self._delay_profile()
        delay.sleep(rng)
        if delay.should_timeout(rng):
            raise TimeoutError("virtual_network_timeout")
        items, next_cursor = self.store.list_transactions(
            since=since,
            until=until,
            cursor=cursor,
            limit=200,
            client_id=getattr(conn, "client_id", None),
        )
        transactions = [
            ProviderTransaction(
                provider_tx_id=item.get("provider_tx_id"),
                provider_card_id=item.get("provider_card_id"),
                occurred_at=datetime.fromisoformat(item["occurred_at"]),
                amount=_parse_decimal(item.get("amount")) or Decimal("0"),
                currency=item.get("currency", "RUB"),
                volume_liters=_parse_decimal(item.get("volume_liters")),
                category=item.get("category"),
                merchant_name=item.get("merchant_name"),
                station_id=item.get("station_id"),
                location=item.get("location"),
                raw_payload=item.get("raw_payload"),
            )
            for item in items
        ]
        return TxPage(items=transactions, next_cursor=next_cursor)

    def fetch_statements(
        self,
        conn,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> ProviderStatement:
        return ProviderStatement(
            provider_statement_id=f"virtual-{period_start.date().isoformat()}-{period_end.date().isoformat()}",
            period_start=period_start,
            period_end=period_end,
            currency="RUB",
            total_in=Decimal("0"),
            total_out=Decimal("0"),
            closing_balance=Decimal("0"),
            lines=[],
            raw_payload={"provider": self.code, "period": [period_start.isoformat(), period_end.isoformat()]},
        )

    def map_transaction(self, item: ProviderTransaction) -> dict:
        normalized_category = normalize_category(item.category)
        payload = item.raw_payload or {}
        return CanonicalTransaction(
            provider_code=self.code,
            provider_tx_id=item.provider_tx_id,
            provider_card_id=item.provider_card_id,
            card_alias=payload.get("card_alias"),
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
        occurred_at = payload.get("occurred_at")
        when = datetime.fromisoformat(occurred_at) if occurred_at else _now()
        return CanonicalTransaction(
            provider_code=self.code,
            provider_tx_id=payload.get("provider_tx_id"),
            provider_card_id=payload.get("provider_card_id"),
            card_alias=payload.get("card_alias"),
            occurred_at=when,
            amount=_parse_decimal(payload.get("amount")) or Decimal("0"),
            currency=payload.get("currency", "RUB"),
            volume_liters=_parse_decimal(payload.get("volume_liters")),
            category=payload.get("category"),
            merchant_name=payload.get("merchant_name"),
            station_id=payload.get("station_id"),
            location=payload.get("location"),
            raw_payload=payload,
        ).__dict__

    def fetch_prices(self, station_ids: list[str]) -> dict[str, dict[str, Decimal]]:
        config = self._config()
        prices = config.get("prices") or {}
        result: dict[str, dict[str, Decimal]] = {}
        for station_id in station_ids:
            station_prices = prices.get(station_id) or {}
            result[station_id] = {product: Decimal(str(value)) for product, value in station_prices.items()}
        return result

    def map_station(self, station: dict[str, Any]) -> dict[str, Any]:
        return {
            "external_id": station.get("station_id"),
            "name": station.get("name"),
            "brand": station.get("brand"),
            "region": station.get("region"),
            "city": station.get("city"),
            "geo": station.get("geo"),
            "services": station.get("services"),
        }

    def map_product(self, product: dict[str, Any]) -> dict[str, Any]:
        return {"code": product.get("code"), "name": product.get("name"), "price": product.get("price")}

    def map_txn(self, txn: dict[str, Any]) -> dict[str, Any]:
        payload = txn.get("raw_payload") or txn
        return {
            "external_id": txn.get("provider_tx_id"),
            "card_alias": payload.get("card_alias"),
            "amount": txn.get("amount"),
            "volume_liters": txn.get("volume_liters"),
            "occurred_at": txn.get("occurred_at"),
        }
