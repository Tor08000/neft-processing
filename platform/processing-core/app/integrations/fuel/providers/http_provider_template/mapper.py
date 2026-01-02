from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.integrations.fuel.base import ProviderStatement, ProviderTransaction
from app.integrations.fuel.normalize import CanonicalStatement, CanonicalTransaction, normalize_category


def map_transaction(*, provider_code: str, item: ProviderTransaction) -> dict:
    normalized_category = normalize_category(item.category)
    return CanonicalTransaction(
        provider_code=provider_code,
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


def map_statement(*, provider_code: str, statement: ProviderStatement) -> dict:
    return CanonicalStatement(
        provider_code=provider_code,
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


def map_raw_event(*, provider_code: str, payload: dict) -> dict:
    occurred_at = payload.get("occurred_at")
    parsed_time = datetime.fromisoformat(occurred_at) if occurred_at else datetime.now(timezone.utc)
    return CanonicalTransaction(
        provider_code=provider_code,
        provider_tx_id=payload.get("id"),
        provider_card_id=payload.get("card_id"),
        card_alias=None,
        occurred_at=parsed_time,
        amount=Decimal(str(payload.get("amount", "0"))),
        currency=payload.get("currency", "RUB"),
        volume_liters=Decimal(str(payload.get("volume_liters", "0"))) if payload.get("volume_liters") else None,
        category=payload.get("category"),
        merchant_name=payload.get("merchant"),
        station_id=payload.get("station_id"),
        location=payload.get("location"),
        raw_payload=payload,
    ).__dict__
