from __future__ import annotations

from app.models.unified_explain import PrimaryReason


PRIMARY_REASON_PRIORITY = [
    PrimaryReason.RISK,
    PrimaryReason.LIMIT,
    PrimaryReason.LOGISTICS,
    PrimaryReason.MONEY,
    PrimaryReason.POLICY,
]

PRIMARY_REASON_SECTION_REQUIREMENTS = {
    PrimaryReason.LIMIT: {"limits"},
    PrimaryReason.RISK: {"risk"},
    PrimaryReason.LOGISTICS: {"logistics", "navigator"},
    PrimaryReason.MONEY: {"money"},
    PrimaryReason.POLICY: {"policy"},
}


def ensure_primary_reason_consistency(
    primary_reason: PrimaryReason,
    *,
    sections: dict[str, object],
) -> PrimaryReason:
    if primary_reason == PrimaryReason.UNKNOWN:
        return primary_reason
    required = PRIMARY_REASON_SECTION_REQUIREMENTS.get(primary_reason)
    if not required:
        return primary_reason
    if primary_reason == PrimaryReason.LOGISTICS:
        if sections.get("logistics") or sections.get("navigator"):
            return primary_reason
        return PrimaryReason.UNKNOWN
    if sections.get(next(iter(required))):
        return primary_reason
    return PrimaryReason.UNKNOWN


__all__ = ["PRIMARY_REASON_PRIORITY", "PRIMARY_REASON_SECTION_REQUIREMENTS", "ensure_primary_reason_consistency"]
