from __future__ import annotations

from typing import Iterable


FUEL_METRIC_KEYS = {"fuel_tx", "fuel_volume", "FUEL_TX_COUNT", "FUEL_VOLUME"}


def tariff_has_fuel_metrics(tariff_definition: dict | None) -> bool:
    if not isinstance(tariff_definition, dict):
        return False
    included = tariff_definition.get("included")
    overage = tariff_definition.get("overage")
    caps = tariff_definition.get("caps")
    metric_rules = tariff_definition.get("metric_rules")

    if _contains_metric_keys(included, FUEL_METRIC_KEYS):
        return True
    if _contains_metric_keys(overage, FUEL_METRIC_KEYS):
        return True
    if _contains_metric_keys(caps, FUEL_METRIC_KEYS):
        return True
    if _metric_rules_include(metric_rules, FUEL_METRIC_KEYS):
        return True
    return False


def _contains_metric_keys(container: object, metrics: set[str]) -> bool:
    if isinstance(container, dict):
        return bool(set(str(key) for key in container.keys()) & metrics)
    if isinstance(container, list):
        for item in container:
            if isinstance(item, dict):
                key = item.get("metric") or item.get("code")
                if key in metrics:
                    return True
    return False


def _metric_rules_include(rules: object, metrics: Iterable[str]) -> bool:
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        condition = rule.get("if")
        if isinstance(condition, dict) and condition.get("metric") in metrics:
            return True
        action = rule.get("then")
        if isinstance(action, dict) and action.get("metric") in metrics:
            return True
    return False


__all__ = ["tariff_has_fuel_metrics"]
