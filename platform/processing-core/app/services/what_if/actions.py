from __future__ import annotations

from dataclasses import dataclass

from app.services.fleet_decision_choice import defaults as decision_choice_defaults
from app.services.what_if import defaults


@dataclass(frozen=True)
class DecisionChoiceActionInfo:
    action_code: str
    confidence: float | None
    cooldown: bool
    cooldown_reason: str | None
    memory_sample_size: int | None
    memory_window_days: int | None


def normalize_action_code(action_code: str) -> str:
    mapped = decision_choice_defaults.ACTION_LABELS.get(action_code, action_code)
    return defaults.ACTION_ALIASES.get(mapped, mapped)


def action_title(action_code: str) -> str:
    normalized = normalize_action_code(action_code)
    return defaults.ACTION_TITLES.get(normalized, normalized.replace("_", " ").title())


def action_deeplink(action_code: str) -> str | None:
    normalized = normalize_action_code(action_code)
    return defaults.ACTION_DEEPLINKS.get(normalized)


def action_category(action_code: str) -> str | None:
    normalized = normalize_action_code(action_code)
    return defaults.ACTION_CATEGORIES.get(normalized)


def list_candidate_actions(
    *,
    suggested_actions: list[str] | None,
    decision_choice: dict | None,
    max_candidates: int,
) -> list[str]:
    if suggested_actions:
        return _dedupe(suggested_actions)[:max_candidates]
    decision_actions = _decision_choice_actions(decision_choice)
    if decision_actions:
        return decision_actions[:max_candidates]
    return _dedupe(defaults.DEFAULT_ACTION_CODES)[:max_candidates]


def extract_decision_choice_info(decision_choice: dict | None) -> dict[str, DecisionChoiceActionInfo]:
    if not isinstance(decision_choice, dict):
        return {}
    actions: list[dict] = []
    recommended = decision_choice.get("recommended_action")
    if isinstance(recommended, dict):
        actions.append(recommended)
    alternatives = decision_choice.get("alternatives")
    if isinstance(alternatives, list):
        actions.extend(item for item in alternatives if isinstance(item, dict))
    info_map: dict[str, DecisionChoiceActionInfo] = {}
    for action in actions:
        action_code = action.get("action_code")
        if not action_code:
            continue
        cooldown_payload = action.get("cooldown") if isinstance(action.get("cooldown"), dict) else {}
        memory_payload = action.get("memory") if isinstance(action.get("memory"), dict) else {}
        info_map[str(action_code)] = DecisionChoiceActionInfo(
            action_code=str(action_code),
            confidence=_coerce_float(action.get("confidence")),
            cooldown=bool(cooldown_payload.get("active", False)),
            cooldown_reason=_coerce_str(cooldown_payload.get("reason")),
            memory_sample_size=_coerce_int(memory_payload.get("sample_size")),
            memory_window_days=_coerce_int(memory_payload.get("window_days")),
        )
    return info_map


def _decision_choice_actions(decision_choice: dict | None) -> list[str]:
    if not isinstance(decision_choice, dict):
        return []
    recommended = decision_choice.get("recommended_action")
    alternatives = decision_choice.get("alternatives")
    ordered: list[str] = []
    if isinstance(recommended, dict) and recommended.get("action_code"):
        ordered.append(str(recommended["action_code"]))
    if isinstance(alternatives, list):
        ordered.extend(
            str(item.get("action_code"))
            for item in alternatives
            if isinstance(item, dict) and item.get("action_code")
        )
    return _dedupe(ordered)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _coerce_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "DecisionChoiceActionInfo",
    "action_category",
    "action_deeplink",
    "action_title",
    "extract_decision_choice_info",
    "list_candidate_actions",
    "normalize_action_code",
]
