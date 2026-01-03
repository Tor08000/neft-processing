from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class OrderSlaEvaluationOut(BaseModel):
    id: str
    order_id: str
    contract_id: str
    obligation_id: str
    period_start: datetime
    period_end: datetime
    measured_value: Decimal
    status: str
    breach_reason: str | None
    breach_severity: str | None
    created_at: datetime


class OrderSlaEvaluationsResponse(BaseModel):
    items: list[OrderSlaEvaluationOut]


class OrderSlaConsequenceOut(BaseModel):
    id: str
    order_id: str
    evaluation_id: str
    consequence_type: str
    amount: Decimal
    currency: str
    billing_invoice_id: str | None
    billing_refund_id: str | None
    ledger_tx_id: str | None
    status: str
    created_at: datetime


class OrderSlaConsequencesResponse(BaseModel):
    items: list[OrderSlaConsequenceOut]
