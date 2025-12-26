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


class RiskOutcome(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_WITH_LOG = "ALLOW_WITH_LOG"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCK = "BLOCK"


class RiskThresholdScope(str, Enum):
    GLOBAL = "GLOBAL"
    TENANT = "TENANT"
    CLIENT = "CLIENT"


class RiskThresholdAction(str, Enum):
    PAYMENT = "PAYMENT"
    INVOICE = "INVOICE"
    PAYOUT = "PAYOUT"
    EXPORT = "EXPORT"
    DOCUMENT_FINALIZE = "DOCUMENT_FINALIZE"


__all__ = [
    "RiskDecisionActor",
    "RiskDecisionType",
    "RiskOutcome",
    "RiskSubjectType",
    "RiskThresholdAction",
    "RiskThresholdScope",
]
