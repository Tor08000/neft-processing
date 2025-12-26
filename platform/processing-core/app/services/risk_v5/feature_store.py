from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.services.decision.context import DecisionContext
from app.services.risk_v5.features import FEATURES_SCHEMA_VERSION, build_feature_vector


@dataclass(frozen=True)
class FeatureSnapshot:
    schema_version: str
    features: dict
    features_hash: str


def build_feature_snapshot(ctx: DecisionContext) -> FeatureSnapshot:
    features = build_feature_vector(ctx)
    features_hash = hash_features(features)
    return FeatureSnapshot(
        schema_version=FEATURES_SCHEMA_VERSION,
        features=features,
        features_hash=features_hash,
    )


def hash_features(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = ["FeatureSnapshot", "build_feature_snapshot", "hash_features"]
