from __future__ import annotations

from importlib import import_module

__all__ = [
    "MoneyFlowError",
    "MoneyFlowNotFound",
    "MoneyFlowTransitionError",
    "MoneyFlowEventType",
    "MoneyFlowState",
    "MoneyFlowType",
    "apply_transition",
    "ensure_money_flow_links",
    "build_explain_snapshot",
    "build_money_explain",
    "build_money_health",
    "MoneyFlowGraphBuilder",
    "MoneyReplayMode",
    "MoneyReplayScope",
    "record_snapshot",
    "run_money_flow_replay",
]


_LAZY_IMPORTS = {
    "build_money_health": "app.services.money_flow.diagnostics",
    "apply_transition": "app.services.money_flow.engine",
    "MoneyFlowError": "app.services.money_flow.errors",
    "MoneyFlowNotFound": "app.services.money_flow.errors",
    "MoneyFlowTransitionError": "app.services.money_flow.errors",
    "MoneyFlowEventType": "app.services.money_flow.events",
    "MoneyFlowState": "app.services.money_flow.states",
    "MoneyFlowType": "app.services.money_flow.states",
    "MoneyFlowGraphBuilder": "app.services.money_flow.graph",
    "ensure_money_flow_links": "app.services.money_flow.graph",
    "build_explain_snapshot": "app.services.money_flow.explain",
    "build_money_explain": "app.services.money_flow.explain",
    "MoneyReplayMode": "app.services.money_flow.replay",
    "MoneyReplayScope": "app.services.money_flow.replay",
    "record_snapshot": "app.services.money_flow.snapshots",
    "run_money_flow_replay": "app.services.money_flow.replay",
}


def __getattr__(name: str):
    module_path = _LAZY_IMPORTS.get(name)
    if not module_path:
        raise AttributeError(f"module 'app.services.money_flow' has no attribute '{name}'")
    module = import_module(module_path)
    return getattr(module, name)
