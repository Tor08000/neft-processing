from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID

from app.services.decision.versions import DecisionAction


def _json_sort_key(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize_payload_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_payload_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (set, frozenset)):
        normalized_items = [_normalize_payload_value(item) for item in value]
        return sorted(normalized_items, key=_json_sort_key)
    if isinstance(value, (list, tuple)):
        return [_normalize_payload_value(item) for item in value]
    return value


@dataclass(frozen=True)
class DecisionContext:
    tenant_id: int
    client_id: str | None
    action: DecisionAction | Enum | str
    actor_type: Literal["CLIENT", "ADMIN", "SYSTEM"] = "SYSTEM"
    actor_id: str | None = None
    amount: int | None = None
    currency: str | None = None
    payment_method: str | None = None
    invoice_id: str | None = None
    billing_period_id: str | None = None
    scoring_rules: list | None = None
    age: int | None = None
    history: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_payload(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "client_id": self.client_id,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "action": self.action.value if hasattr(self.action, "value") else self.action,
            "amount": self.amount,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "invoice_id": self.invoice_id,
            "billing_period_id": self.billing_period_id,
            "age": self.age,
            "history": _normalize_payload_value(self.history),
            "metadata": _normalize_payload_value(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, ensure_ascii=False)
