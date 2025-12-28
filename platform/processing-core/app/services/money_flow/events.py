from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from app.services.money_flow.states import MoneyFlowState, MoneyFlowType


class MoneyFlowEventType(str, Enum):
    AUTHORIZE = "AUTHORIZE"
    SETTLE = "SETTLE"
    REVERSE = "REVERSE"
    DISPUTE_OPEN = "DISPUTE_OPEN"
    DISPUTE_RESOLVE = "DISPUTE_RESOLVE"
    FAIL = "FAIL"
    CANCEL = "CANCEL"


@dataclass(frozen=True)
class MoneyFlowEventData:
    flow_type: MoneyFlowType
    flow_ref_id: str
    state_from: MoneyFlowState | None
    state_to: MoneyFlowState
    event_type: MoneyFlowEventType
    idempotency_key: str
    ledger_transaction_id: str | None = None
    risk_decision_id: str | None = None
    reason_code: str | None = None
    explain_snapshot: Mapping[str, Any] | None = None
    meta: Mapping[str, Any] | None = None


__all__ = ["MoneyFlowEventData", "MoneyFlowEventType"]
