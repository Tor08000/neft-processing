from __future__ import annotations

from enum import Enum


class RiskSubjectType(str, Enum):
    PAYMENT = "PAYMENT"
    INVOICE = "INVOICE"
    PAYOUT = "PAYOUT"
    DOCUMENT = "DOCUMENT"
    EXPORT = "EXPORT"


class RiskDecisionType(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_WITH_REVIEW = "ALLOW_WITH_REVIEW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class RiskDecisionActor(str, Enum):
    SYSTEM = "SYSTEM"
    ADMIN = "ADMIN"


__all__ = ["RiskDecisionActor", "RiskDecisionType", "RiskSubjectType"]
