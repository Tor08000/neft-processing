from __future__ import annotations

from app.models.unified_explain import PrimaryReason
from app.services.explain.actions.base import ActionHint, ActionItem


class RiskActionHint(ActionHint):
    primary_reason = PrimaryReason.RISK

    def build(self, explain=None) -> list[ActionItem]:
        return [
            ActionItem(
                code="REQUEST_OVERRIDE",
                title="Request risk override",
                description="Operation blocked by risk policy",
                target="COMPLIANCE",
                severity="REQUIRED",
            )
        ]


__all__ = ["RiskActionHint"]
