from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UnifiedExplainView(str, Enum):
    FLEET = "FLEET"
    ACCOUNTANT = "ACCOUNTANT"
    FULL = "FULL"


class UnifiedExplainSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    id: str
    ts: str | None = None
    client_id: str | None = None
    vehicle_id: str | None = None
    driver_id: str | None = None


class UnifiedExplainResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    primary_reason: str | None = None
    decline_code: str | None = None


class UnifiedExplainIds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_decision_id: str | None = None
    ledger_transaction_id: str | None = None
    invoice_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    money_flow_event_ids: list[str] = Field(default_factory=list)
    snapshot_id: str | None = None
    snapshot_hash: str | None = None


class UnifiedExplainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: UnifiedExplainSubject
    result: UnifiedExplainResult
    sections: dict[str, Any]
    ids: UnifiedExplainIds
    recommendations: list[str]


__all__ = [
    "UnifiedExplainIds",
    "UnifiedExplainResponse",
    "UnifiedExplainResult",
    "UnifiedExplainSubject",
    "UnifiedExplainView",
]
