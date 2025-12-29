from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models.fleet_intelligence import FITrendLabel
from app.schemas.admin import unified_explain as projection_types
from app.services.fleet_intelligence.control import defaults as control_defaults


DEFAULT_TIME_WINDOW_DAYS = 7


@dataclass(frozen=True)
class KPIEstimate:
    kpi: str
    direction: str
    estimate: str


_DRIVER_SCORE_RANGES = {
    "IMPROVED": "5–12 points",
    "NO_CHANGE": "0–3 points",
    "WORSE": "0–8 points up",
}
_STATION_TRUST_RANGES = {
    "IMPROVED": "5–12 points",
    "NO_CHANGE": "0–3 points",
    "WORSE": "0–8 points down",
}
_VEHICLE_EFFICIENCY_RANGES = {
    "IMPROVED": "5–12%",
    "NO_CHANGE": "0–3%",
    "WORSE": "0–8% up",
}

_TREND_BASELINES = {
    FITrendLabel.DEGRADING.value: 40,
    FITrendLabel.STABLE.value: 20,
    FITrendLabel.IMPROVING.value: 10,
}


def build_outcome_projection(
    *,
    confidence: float | None,
    sample_size: int | None,
    trend_label: str | None,
    entity_type: str | None,
    sla_remaining_minutes: int | None,
    aging_days: int | None,
    insight_status: str | None,
    half_life_days: int | None = None,
    time_window_days: int = DEFAULT_TIME_WINDOW_DAYS,
) -> projection_types.FleetAssistantProjection:
    resolved_trend = _normalize_trend_label(trend_label)
    applied = _build_if_applied(
        confidence=confidence,
        sample_size=sample_size,
        trend_label=resolved_trend,
        entity_type=entity_type,
        half_life_days=half_life_days or control_defaults.CONF_HALF_LIFE_DAYS,
        time_window_days=time_window_days,
    )
    ignored = _build_if_ignored(
        trend_label=resolved_trend,
        entity_type=entity_type,
        sla_remaining_minutes=sla_remaining_minutes,
        aging_days=aging_days,
        insight_status=insight_status,
    )
    return projection_types.FleetAssistantProjection(if_applied=applied, if_ignored=ignored)


def _build_if_applied(
    *,
    confidence: float | None,
    sample_size: int | None,
    trend_label: str,
    entity_type: str | None,
    half_life_days: int,
    time_window_days: int,
) -> projection_types.FleetAssistantProjectionApplied:
    resolved_confidence = max(confidence or 0.0, 0.0)
    probability_improved_pct = round(100 * resolved_confidence)
    expected_effect_label = _label_from_confidence(resolved_confidence)
    expected_kpis = _build_expected_kpis(entity_type, expected_effect_label)
    basis = projection_types.FleetAssistantProjectionAppliedBasis(
        confidence=round(resolved_confidence, 2),
        sample_size=int(sample_size or 0),
        half_life_days=half_life_days,
        trend_label=trend_label,
    )
    return projection_types.FleetAssistantProjectionApplied(
        probability_improved_pct=probability_improved_pct,
        expected_effect_label=expected_effect_label,
        expected_time_window_days=time_window_days,
        expected_kpis=expected_kpis,
        basis=basis,
    )


def _build_if_ignored(
    *,
    trend_label: str,
    entity_type: str | None,
    sla_remaining_minutes: int | None,
    aging_days: int | None,
    insight_status: str | None,
) -> projection_types.FleetAssistantProjectionIgnored:
    baseline = _TREND_BASELINES.get(trend_label, 20)
    probability_worse_pct = baseline
    if sla_remaining_minutes is not None and sla_remaining_minutes < 720:
        probability_worse_pct += 10
    if aging_days is not None and aging_days >= 10:
        probability_worse_pct += 10
    expected_effect_label = _label_from_trend(trend_label)
    expected_kpis = _build_ignored_kpis(trend_label, entity_type)
    escalation_risk = _build_escalation_risk(
        sla_remaining_minutes=sla_remaining_minutes,
        aging_days=aging_days,
        insight_status=insight_status,
    )
    basis = projection_types.FleetAssistantProjectionIgnoredBasis(
        trend_label=trend_label,
        aging_days=aging_days,
        sla_remaining_minutes=sla_remaining_minutes,
    )
    return projection_types.FleetAssistantProjectionIgnored(
        probability_worse_pct=probability_worse_pct,
        expected_effect_label=expected_effect_label,
        escalation_risk=escalation_risk,
        expected_kpis=expected_kpis,
        basis=basis,
    )


def _normalize_trend_label(label: str | None) -> str:
    if not label:
        return FITrendLabel.UNKNOWN.value
    normalized = label.upper()
    if normalized in {item.value for item in FITrendLabel}:
        return normalized
    return FITrendLabel.UNKNOWN.value


def _label_from_confidence(confidence: float) -> str:
    if confidence >= 0.6:
        return "IMPROVED"
    if confidence >= 0.35:
        return "NO_CHANGE"
    return "WORSE"


def _label_from_trend(trend_label: str) -> str:
    if trend_label == FITrendLabel.DEGRADING.value:
        return "WORSE"
    if trend_label == FITrendLabel.IMPROVING.value:
        return "IMPROVED"
    return "NO_CHANGE"


def _build_expected_kpis(
    entity_type: str | None,
    expected_effect_label: str,
) -> list[projection_types.FleetAssistantProjectionKPI]:
    estimates = list(_build_kpi_estimates(entity_type, expected_effect_label))
    return [projection_types.FleetAssistantProjectionKPI(**estimate.__dict__) for estimate in estimates]


def _build_ignored_kpis(
    trend_label: str,
    entity_type: str | None,
) -> list[projection_types.FleetAssistantProjectionKPI]:
    if trend_label != FITrendLabel.DEGRADING.value:
        return []
    return [
        projection_types.FleetAssistantProjectionKPI(
            kpi="risk_blocks",
            direction="UP",
            estimate="possible",
        )
    ]


def _build_kpi_estimates(entity_type: str | None, expected_effect_label: str) -> Iterable[KPIEstimate]:
    if entity_type == "DRIVER":
        yield _driver_score_estimate(expected_effect_label)
    elif entity_type == "STATION":
        yield _station_trust_estimate(expected_effect_label)
    elif entity_type == "VEHICLE":
        yield _vehicle_efficiency_estimate(expected_effect_label)


def _driver_score_estimate(label: str) -> KPIEstimate:
    direction = "DOWN" if label == "IMPROVED" else "UP" if label == "WORSE" else "FLAT"
    return KPIEstimate(
        kpi="driver_score",
        direction=direction,
        estimate=_DRIVER_SCORE_RANGES[label],
    )


def _station_trust_estimate(label: str) -> KPIEstimate:
    direction = "UP" if label == "IMPROVED" else "DOWN" if label == "WORSE" else "FLAT"
    return KPIEstimate(
        kpi="station_trust",
        direction=direction,
        estimate=_STATION_TRUST_RANGES[label],
    )


def _vehicle_efficiency_estimate(label: str) -> KPIEstimate:
    direction = "DOWN" if label == "IMPROVED" else "UP" if label == "WORSE" else "FLAT"
    return KPIEstimate(
        kpi="vehicle_efficiency_delta_pct",
        direction=direction,
        estimate=_VEHICLE_EFFICIENCY_RANGES[label],
    )


def _build_escalation_risk(
    *,
    sla_remaining_minutes: int | None,
    aging_days: int | None,
    insight_status: str | None,
) -> projection_types.FleetAssistantProjectionEscalationRisk:
    sla_risk = sla_remaining_minutes is not None and sla_remaining_minutes <= 1440
    aging_risk = aging_days is not None and aging_days >= 14 and (insight_status or "").upper() == "OPEN"
    if sla_risk and aging_risk:
        reason = "SLA expires and aging rule triggers escalation"
    elif sla_risk:
        reason = "SLA expires soon"
    elif aging_risk:
        reason = "Aging rule triggers escalation"
    else:
        reason = "no SLA" if sla_remaining_minutes is None else "no escalation trigger"
    return projection_types.FleetAssistantProjectionEscalationRisk(
        likely=bool(sla_risk or aging_risk),
        eta_minutes=sla_remaining_minutes,
        reason=reason,
    )


__all__ = [
    "DEFAULT_TIME_WINDOW_DAYS",
    "build_outcome_projection",
]
