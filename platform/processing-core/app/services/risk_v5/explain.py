from __future__ import annotations

from app.services.risk_v5.feature_store import FeatureSnapshot
from app.services.risk_v5.scorer import RiskV5Score


def build_explain(*, snapshot: FeatureSnapshot, score: RiskV5Score) -> dict:
    impacts = score.feature_impacts
    top_features = sorted(
        (
            {
                "name": name,
                "value": snapshot.features.get(name),
                "impact": impact,
            }
            for name, impact in impacts.items()
        ),
        key=lambda item: abs(item["impact"]),
        reverse=True,
    )
    return {
        "model_version": score.model_version,
        "features_schema_version": snapshot.schema_version,
        "top_features": top_features[:5],
        "score": score.score,
    }


__all__ = ["build_explain"]
