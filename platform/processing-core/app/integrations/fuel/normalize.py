from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.schemas.fleet_ingestion import FleetIngestItemIn
from app.services.case_event_redaction import redact_deep

CATEGORY_MAP = {
    "FUEL": "FUEL",
    "WASH": "WASH",
    "TOLL": "TOLL",
    "SHOP": "SHOP",
    "SERVICE": "SERVICE",
    "OTHER": "OTHER",
}

MERCHANT_KEY_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class CanonicalTransaction:
    provider_code: str
    provider_tx_id: str | None
    provider_card_id: str | None
    card_alias: str | None
    occurred_at: datetime
    amount: Decimal
    currency: str
    volume_liters: Decimal | None
    category: str | None
    merchant_name: str | None
    station_id: str | None
    location: str | None
    raw_payload: dict[str, Any] | None


@dataclass(frozen=True)
class CanonicalStatement:
    provider_code: str
    provider_statement_id: str | None
    period_start: datetime
    period_end: datetime
    currency: str
    total_in: Decimal | None
    total_out: Decimal | None
    closing_balance: Decimal | None
    lines: list[dict] | None
    raw_payload: dict[str, Any] | None


@dataclass(frozen=True)
class NormalizedCategory:
    value: str
    is_unknown: bool


def normalize_category(raw: str | None) -> NormalizedCategory:
    if not raw:
        return NormalizedCategory(value="OTHER", is_unknown=True)
    normalized = raw.strip().upper()
    mapped = CATEGORY_MAP.get(normalized)
    if mapped:
        return NormalizedCategory(value=mapped, is_unknown=False)
    return NormalizedCategory(value="OTHER", is_unknown=True)


def normalize_merchant_key(name: str | None, station_id: str | None) -> str | None:
    value = name or station_id
    if not value:
        return None
    lowered = value.strip().lower()
    normalized = MERCHANT_KEY_PATTERN.sub("", lowered)
    return normalized or lowered


def canonical_to_ingest_item(canonical: CanonicalTransaction, *, client_ref: str | None) -> FleetIngestItemIn:
    return FleetIngestItemIn(
        provider_tx_id=canonical.provider_tx_id,
        client_ref=client_ref,
        card_alias=canonical.card_alias,
        occurred_at=canonical.occurred_at,
        amount=canonical.amount,
        currency=canonical.currency,
        volume_liters=canonical.volume_liters,
        category=canonical.category,
        merchant_name=canonical.merchant_name,
        station_id=canonical.station_id,
        location=canonical.location,
        external_ref=canonical.provider_tx_id,
        raw_payload=canonical.raw_payload,
    )


def redact_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    return redact_deep(payload, "", include_hash=True)


def payload_hash(payload: dict[str, Any] | None) -> str:
    data = payload or {}
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = [
    "CanonicalStatement",
    "CanonicalTransaction",
    "NormalizedCategory",
    "canonical_to_ingest_item",
    "normalize_category",
    "normalize_merchant_key",
    "payload_hash",
    "redact_payload",
]
