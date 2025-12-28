from __future__ import annotations

from app.models.unified_explain import PrimaryReason


PRIMARY_REASON_PRIORITY = [
    PrimaryReason.RISK,
    PrimaryReason.LIMIT,
    PrimaryReason.LOGISTICS,
    PrimaryReason.MONEY,
    PrimaryReason.POLICY,
]


__all__ = ["PRIMARY_REASON_PRIORITY"]
