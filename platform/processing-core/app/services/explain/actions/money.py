from __future__ import annotations

from app.models.unified_explain import PrimaryReason
from app.services.explain.actions.base import ActionHint, ActionItem


class MoneyActionHint(ActionHint):
    primary_reason = PrimaryReason.MONEY

    def build(self, explain=None) -> list[ActionItem]:
        return []


__all__ = ["MoneyActionHint"]
