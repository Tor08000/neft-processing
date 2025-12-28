from __future__ import annotations

from dataclasses import dataclass

from app.models.crm import CRMUsageMetric


@dataclass(frozen=True)
class MetricRuleResult:
    overage_prices: dict[str, int]
    base_fee_adjustments: list[int]
    applied_rules: list[dict]


def apply_metric_rules(
    *,
    usage_by_metric: dict[str, int],
    overage_prices: dict[str, int],
    rules: list[dict] | None,
) -> MetricRuleResult:
    rules = rules or []
    updated_prices = dict(overage_prices)
    base_fee_adjustments: list[int] = []
    applied: list[dict] = []

    for rule in rules:
        condition = rule.get("if") or {}
        metric = condition.get("metric")
        if not metric:
            continue
        metric_value = usage_by_metric.get(metric, 0)
        if not _matches_condition(metric_value, condition):
            continue
        action = rule.get("then") or {}
        if "set_overage_price_minor" in action:
            updated_prices[action.get("metric", metric)] = int(action.get("set_overage_price_minor") or 0)
        if "add_base_fee_minor" in action:
            base_fee_adjustments.append(int(action.get("add_base_fee_minor") or 0))
        applied.append(rule)
    return MetricRuleResult(
        overage_prices=updated_prices,
        base_fee_adjustments=base_fee_adjustments,
        applied_rules=applied,
    )


def _matches_condition(value: int, condition: dict) -> bool:
    op = condition.get("op")
    threshold = condition.get("value")
    if threshold is None:
        return False
    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold
    if op == "==":
        return value == threshold
    return False


def metric_key(metric: CRMUsageMetric | str) -> str:
    value = metric.value if isinstance(metric, CRMUsageMetric) else metric
    return value


__all__ = ["MetricRuleResult", "apply_metric_rules", "metric_key"]
