from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RecommendationRequest:
    client_id: str
    context: dict | None = None


@dataclass(frozen=True)
class RecommendationScore:
    product_id: str
    score: Decimal


class RecommendationsModel:
    def predict(self, request: RecommendationRequest) -> list[RecommendationScore]:
        raise NotImplementedError("recommendation_model_not_configured")


__all__ = ["RecommendationRequest", "RecommendationScore", "RecommendationsModel"]
