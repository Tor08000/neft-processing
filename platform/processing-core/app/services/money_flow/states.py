from __future__ import annotations

from enum import Enum


class MoneyFlowState(str, Enum):
    DRAFT = "DRAFT"
    AUTHORIZED = "AUTHORIZED"
    PENDING_SETTLEMENT = "PENDING_SETTLEMENT"
    SETTLED = "SETTLED"
    REVERSED = "REVERSED"
    DISPUTED = "DISPUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MoneyFlowType(str, Enum):
    FUEL_TX = "FUEL_TX"
    SUBSCRIPTION_CHARGE = "SUBSCRIPTION_CHARGE"
    INVOICE_PAYMENT = "INVOICE_PAYMENT"
    REFUND = "REFUND"
    PAYOUT = "PAYOUT"


__all__ = ["MoneyFlowState", "MoneyFlowType"]
