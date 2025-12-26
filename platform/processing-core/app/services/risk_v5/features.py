from __future__ import annotations

from app.services.decision.context import DecisionContext

FEATURES_SCHEMA_VERSION = "v1"


def build_feature_vector(ctx: DecisionContext) -> dict:
    history = ctx.history or {}
    metadata = ctx.metadata or {}
    return {
        "amount": ctx.amount or 0,
        "currency": ctx.currency or "UNK",
        "client_age_days": metadata.get("client_age_days") or ctx.age or 0,
        "txn_count_24h": history.get("txn_count_24h", 0),
        "avg_amount_7d": history.get("avg_amount_7d", 0),
        "velocity_spike": bool(history.get("velocity_spike", False)),
        "provider_risk_level": metadata.get("provider_risk_level", "UNKNOWN"),
        "last_blocked_days": history.get("last_blocked_days", 0),
        "settlement_anomalies": bool(metadata.get("settlement_anomalies", False)),
    }


__all__ = ["FEATURES_SCHEMA_VERSION", "build_feature_vector"]
