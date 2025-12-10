from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field


class OperationSchema(BaseModel):
    id: Optional[UUID] = None
    operation_id: str
    ext_operation_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    operation_type: str
    status: str

    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str
    product_id: Optional[str] = None

    amount: int
    amount_settled: Optional[int] = None
    currency: str = "RUB"
    product_type: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    captured_amount: int = 0
    refunded_amount: int = 0

    daily_limit: Optional[int] = None
    limit_per_tx: Optional[int] = None
    used_today: Optional[int] = None
    new_used_today: Optional[int] = None
    limit_profile_id: Optional[str] = None
    limit_check_result: Optional[dict] = None

    authorized: bool = False
    response_code: str = "00"
    response_message: str = "OK"
    auth_code: Optional[str] = None

    parent_operation_id: Optional[str] = None
    reason: Optional[str] = None

    mcc: Optional[str] = None
    product_code: Optional[str] = None
    product_category: Optional[str] = None
    tx_type: Optional[str] = None
    risk_score: Optional[float] = None
    risk_result: Optional[str] = None
    risk_payload: Optional[dict] = None

    @computed_field
    @property
    def risk_flags(self) -> Optional[dict]:
        payload = self.risk_payload or {}
        flags = payload.get("flags") if isinstance(payload, dict) else None
        return flags

    @computed_field
    @property
    def risk_reasons(self) -> Optional[List[str]]:
        payload = self.risk_payload or {}
        reasons = payload.get("reasons") if isinstance(payload, dict) else None
        if reasons is None and isinstance(payload, dict):
            reasons = payload.get("reason_codes")
        if reasons is None and isinstance(payload, dict):
            decision = payload.get("decision")
            if isinstance(decision, dict):
                reasons = decision.get("reason_codes")
        if reasons is None:
            return None
        return list(reasons)

    @computed_field
    @property
    def risk_source(self) -> Optional[str]:
        payload = self.risk_payload or {}
        if not isinstance(payload, dict):
            return None
        return payload.get("source") or payload.get("engine")

    @computed_field
    @property
    def risk_rules_fired(self) -> Optional[List[str]]:
        payload = self.risk_payload or {}
        if not isinstance(payload, dict):
            return None
        rules = payload.get("rules_fired")
        if rules is None:
            decision = payload.get("decision")
            if isinstance(decision, dict):
                rules = decision.get("rules_fired")
        if rules is None:
            return None
        return list(rules)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class OperationsPage(BaseModel):
    items: List[OperationSchema]
    total: int
    limit: int
    offset: int


class OperationTimeline(BaseModel):
    root: OperationSchema
    children: List[OperationSchema]


# Удобный псевдоним для журнала транзакций
TransactionLogPage = OperationsPage
