from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from app.services.decision.versions import DecisionAction


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
            "history": self.history,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, ensure_ascii=False)
