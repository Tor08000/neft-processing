from __future__ import annotations

from app.models.unified_explain import PrimaryReason
from app.services.explain.actions.base import ActionItem
from app.services.explain.actions.limit import LimitActionHint
from app.services.explain.actions.logistics import LogisticsActionHint
from app.services.explain.actions.money import MoneyActionHint
from app.services.explain.actions.risk import RiskActionHint


_ACTION_HINTS = {
    PrimaryReason.LIMIT: LimitActionHint(),
    PrimaryReason.RISK: RiskActionHint(),
    PrimaryReason.LOGISTICS: LogisticsActionHint(),
    PrimaryReason.MONEY: MoneyActionHint(),
}


def build_actions(primary_reason: PrimaryReason, explain=None) -> list[ActionItem]:
    hint = _ACTION_HINTS.get(primary_reason)
    if not hint:
        return []
    return hint.build(explain)


__all__ = ["build_actions"]
