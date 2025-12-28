from __future__ import annotations

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


def is_valid_ack_reason(code: str) -> bool:
    return code in ACK_REASON_CODES


def is_valid_close_reason(code: str) -> bool:
    return code in CLOSE_REASON_CODES


__all__ = [
    "ACK_REASON_CODES",
    "CLOSE_REASON_CODES",
    "is_valid_ack_reason",
    "is_valid_close_reason",
]
