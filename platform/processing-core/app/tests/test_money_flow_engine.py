from app.services.money_flow.engine import apply_transition
from app.services.money_flow.events import MoneyFlowEventType
from app.services.money_flow.errors import MoneyFlowTransitionError
from app.services.money_flow.explain import build_explain_snapshot
from app.services.money_flow.states import MoneyFlowState


def test_apply_transition_valid():
    result = apply_transition(MoneyFlowState.DRAFT, MoneyFlowEventType.AUTHORIZE)
    assert result.state == MoneyFlowState.AUTHORIZED
    assert result.idempotent is False


def test_apply_transition_idempotent_settle():
    result = apply_transition(MoneyFlowState.SETTLED, MoneyFlowEventType.SETTLE)
    assert result.state == MoneyFlowState.SETTLED
    assert result.idempotent is True


def test_apply_transition_invalid():
    try:
        apply_transition(MoneyFlowState.DRAFT, MoneyFlowEventType.REVERSE)
    except MoneyFlowTransitionError as exc:
        assert "invalid_transition" in str(exc)
    else:
        raise AssertionError("Expected MoneyFlowTransitionError")


def test_explain_snapshot_deterministic():
    payload_a = {"b": 1, "a": {"x": 2, "y": 3}}
    payload_b = {"a": {"y": 3, "x": 2}, "b": 1}

    snapshot_a = build_explain_snapshot(payload_a)
    snapshot_b = build_explain_snapshot(payload_b)

    assert snapshot_a["hash"] == snapshot_b["hash"]
    assert snapshot_a["payload"] == snapshot_b["payload"]
