from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, JSON, String, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.services.money_flow.events import MoneyFlowEventType
from app.services.money_flow.states import MoneyFlowState, MoneyFlowType


class MoneyFlowEvent(Base):
    __tablename__ = "money_flow_events"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    tenant_id = Column(Integer, nullable=False)
    client_id = Column(String(64), nullable=False)
    flow_type = Column(ExistingEnum(MoneyFlowType, name="money_flow_type"), nullable=False)
    flow_ref_id = Column(String(64), nullable=False)
    state_from = Column(ExistingEnum(MoneyFlowState, name="money_flow_state"), nullable=True)
    state_to = Column(ExistingEnum(MoneyFlowState, name="money_flow_state"), nullable=False)
    event_type = Column(ExistingEnum(MoneyFlowEventType, name="money_flow_event_type"), nullable=False)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    ledger_transaction_id = Column(GUID(), nullable=True, index=True)
    risk_decision_id = Column(GUID(), nullable=True, index=True)
    reason_code = Column(String(128), nullable=True)
    explain_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)


__all__ = ["MoneyFlowEvent"]
