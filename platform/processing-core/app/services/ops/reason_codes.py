from __future__ import annotations

from enum import Enum

from app.models.ops import OpsEscalationTarget
from app.models.unified_explain import PrimaryReason

ACK_REASON_CODES = {
    "ACK_IN_REVIEW",
    "ACK_WAITING_CLIENT",
    "ACK_WAITING_INTERNAL",
    "ACK_NEED_MORE_DATA",
    "ACK_ESCALATED",
}

CLOSE_REASON_CODES = {
    "CLOSE_LIMIT_INCREASED",
    "CLOSE_OVERRIDE_APPROVED",
    "CLOSE_ROUTE_ADJUSTED",
    "CLOSE_PAYMENT_RECEIVED",
    "CLOSE_FALSE_POSITIVE",
    "CLOSE_DUPLICATE",
    "CLOSE_OTHER",
}


class OpsReasonCode(str, Enum):
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    LIMIT_PERIOD_MISMATCH = "LIMIT_PERIOD_MISMATCH"
    RISK_BLOCK = "RISK_BLOCK"
    RISK_REVIEW_REQUIRED = "RISK_REVIEW_REQUIRED"
    LOGISTICS_DEVIATION = "LOGISTICS_DEVIATION"
    LOGISTICS_STOP_MISUSE = "LOGISTICS_STOP_MISUSE"
    MONEY_INVARIANT_VIOLATION = "MONEY_INVARIANT_VIOLATION"
    SUBSCRIPTION_LIMIT = "SUBSCRIPTION_LIMIT"
    FEATURE_DISABLED = "FEATURE_DISABLED"


OPS_REASON_CODE_TARGETS: dict[OpsReasonCode, OpsEscalationTarget] = {
    OpsReasonCode.LIMIT_EXCEEDED: OpsEscalationTarget.CRM,
    OpsReasonCode.LIMIT_PERIOD_MISMATCH: OpsEscalationTarget.CRM,
    OpsReasonCode.SUBSCRIPTION_LIMIT: OpsEscalationTarget.CRM,
    OpsReasonCode.FEATURE_DISABLED: OpsEscalationTarget.CRM,
    OpsReasonCode.RISK_BLOCK: OpsEscalationTarget.COMPLIANCE,
    OpsReasonCode.RISK_REVIEW_REQUIRED: OpsEscalationTarget.COMPLIANCE,
    OpsReasonCode.LOGISTICS_DEVIATION: OpsEscalationTarget.LOGISTICS,
    OpsReasonCode.LOGISTICS_STOP_MISUSE: OpsEscalationTarget.LOGISTICS,
    OpsReasonCode.MONEY_INVARIANT_VIOLATION: OpsEscalationTarget.FINANCE,
}

OPS_REASON_CODE_PRIMARY: dict[OpsReasonCode, PrimaryReason] = {
    OpsReasonCode.LIMIT_EXCEEDED: PrimaryReason.LIMIT,
    OpsReasonCode.LIMIT_PERIOD_MISMATCH: PrimaryReason.LIMIT,
    OpsReasonCode.SUBSCRIPTION_LIMIT: PrimaryReason.LIMIT,
    OpsReasonCode.FEATURE_DISABLED: PrimaryReason.POLICY,
    OpsReasonCode.RISK_BLOCK: PrimaryReason.RISK,
    OpsReasonCode.RISK_REVIEW_REQUIRED: PrimaryReason.RISK,
    OpsReasonCode.LOGISTICS_DEVIATION: PrimaryReason.LOGISTICS,
    OpsReasonCode.LOGISTICS_STOP_MISUSE: PrimaryReason.LOGISTICS,
    OpsReasonCode.MONEY_INVARIANT_VIOLATION: PrimaryReason.MONEY,
}


def is_valid_ack_reason(code: str) -> bool:
    return code in ACK_REASON_CODES


def is_valid_close_reason(code: str) -> bool:
    return code in CLOSE_REASON_CODES


def is_valid_ops_reason(code: str) -> bool:
    try:
        OpsReasonCode(code)
    except ValueError:
        return False
    return True


def get_primary_reason(code: OpsReasonCode) -> PrimaryReason:
    return OPS_REASON_CODE_PRIMARY[code]


def get_target_for_reason(code: OpsReasonCode) -> OpsEscalationTarget:
    return OPS_REASON_CODE_TARGETS[code]


__all__ = [
    "ACK_REASON_CODES",
    "CLOSE_REASON_CODES",
    "OpsReasonCode",
    "OPS_REASON_CODE_PRIMARY",
    "OPS_REASON_CODE_TARGETS",
    "get_primary_reason",
    "get_target_for_reason",
    "is_valid_ack_reason",
    "is_valid_close_reason",
    "is_valid_ops_reason",
]
