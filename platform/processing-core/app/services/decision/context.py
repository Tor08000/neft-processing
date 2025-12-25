from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from app.services.decision.versions import DecisionAction


@dataclass(frozen=True)
class DecisionContext:
    tenant_id: int
    client_id: str | None
    actor_type: Literal["CLIENT", "ADMIN", "SYSTEM"]
    action: DecisionAction
    amount: int | None = None
    currency: str | None = None
    payment_method: str | None = None
    invoice_id: str | None = None
    billing_period_id: str | None = None
    history: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_payload(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "client_id": self.client_id,
            "actor_type": self.actor_type,
            "action": self.action.value,
            "amount": self.amount,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "invoice_id": self.invoice_id,
            "billing_period_id": self.billing_period_id,
            "history": self.history,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, ensure_ascii=False)
