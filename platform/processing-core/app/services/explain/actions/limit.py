from __future__ import annotations

from app.models.unified_explain import PrimaryReason
from app.services.explain.actions.base import ActionHint, ActionItem


class LimitActionHint(ActionHint):
    primary_reason = PrimaryReason.LIMIT

    def build(self, explain=None) -> list[ActionItem]:
        return [
            ActionItem(
                code="INCREASE_LIMIT",
                title="Increase limit",
                description="Fuel limit exceeded for this period",
                target="CRM",
                severity="REQUIRED",
            )
        ]


__all__ = ["LimitActionHint"]
