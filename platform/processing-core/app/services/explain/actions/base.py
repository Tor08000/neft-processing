from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from app.models.unified_explain import PrimaryReason

if TYPE_CHECKING:
    from app.schemas.admin.unified_explain import UnifiedExplainResponse


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    title: str
    description: str
    target: str | None
    severity: Literal["INFO", "REQUIRED"]


class ActionHint(Protocol):
    primary_reason: PrimaryReason

    def build(self, explain: UnifiedExplainResponse | None = None) -> list[ActionItem]:
        ...


__all__ = ["ActionHint", "ActionItem"]
