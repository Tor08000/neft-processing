from __future__ import annotations

from app.services.fleet_decision_choice import defaults


def list_candidate_actions(candidate_actions: list[str] | None = None) -> list[str]:
    if candidate_actions:
        return list(dict.fromkeys(candidate_actions))
    return list(defaults.DEFAULT_ACTION_CODES)


__all__ = ["list_candidate_actions"]
