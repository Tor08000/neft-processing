from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field


def _normalize_risk_level(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).upper()
    if normalized in {"ALLOW", "LOW"}:
        return "LOW"
    if normalized == "MEDIUM":
        return "MEDIUM"
    if normalized in {"REVIEW", "MANUAL_REVIEW"}:
        return "MANUAL_REVIEW"
    if normalized == "HIGH":
        return "HIGH"
    if normalized in {"HARD_DECLINE"}:
        return "HARD_DECLINE"
    if normalized in {"BLOCK", "DENY", "DECLINE"}:
        return "BLOCK"
    return normalized


def extract_risk_level(risk_payload: Optional[dict], risk_result: Optional[str]) -> Optional[str]:
    payload = risk_payload or {}
    level = None
    if isinstance(payload, dict):
        decision = payload.get("decision")
        if isinstance(decision, dict):
            level = decision.get("level")
        if level is None:
            level = payload.get("level")
    if level is None:
        level = risk_result
    return _normalize_risk_level(level)


def extract_risk_flags(risk_payload: Optional[dict]) -> Optional[dict]:
    payload = risk_payload or {}
    flags = payload.get("flags") if isinstance(payload, dict) else None
    return flags


def extract_risk_reasons(risk_payload: Optional[dict]) -> Optional[List[str]]:
    payload = risk_payload or {}
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


def extract_risk_source(risk_payload: Optional[dict]) -> Optional[str]:
    payload = risk_payload or {}
    if not isinstance(payload, dict):
        return None
    return payload.get("source") or payload.get("engine")


def extract_risk_rules_fired(risk_payload: Optional[dict]) -> Optional[List[str]]:
    payload = risk_payload or {}
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
        return extract_risk_flags(self.risk_payload)

    @computed_field
    @property
    def risk_reasons(self) -> Optional[List[str]]:
        return extract_risk_reasons(self.risk_payload)

    @computed_field
    @property
    def risk_source(self) -> Optional[str]:
        return extract_risk_source(self.risk_payload)

    @computed_field
    @property
    def risk_rules_fired(self) -> Optional[List[str]]:
        return extract_risk_rules_fired(self.risk_payload)

    @computed_field
    @property
    def risk_level(self) -> Optional[str]:
        return extract_risk_level(self.risk_payload, self.risk_result)

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
