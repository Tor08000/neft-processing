from __future__ import annotations

from app.models.unified_explain import PrimaryReason
from app.services.explain.actions.base import ActionHint, ActionItem


class LogisticsActionHint(ActionHint):
    primary_reason = PrimaryReason.LOGISTICS

    def build(self, explain=None) -> list[ActionItem]:
        return [
            ActionItem(
                code="ADJUST_ROUTE",
                title="Adjust route",
                description="Fuel usage detected outside approved route",
                target="ROUTES",
                severity="INFO",
            )
        ]


__all__ = ["LogisticsActionHint"]
