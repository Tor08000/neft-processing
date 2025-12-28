from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.services.money_flow.errors import MoneyFlowTransitionError
from app.services.money_flow.events import MoneyFlowEventType
from app.services.money_flow.states import MoneyFlowState


@dataclass(frozen=True)
class TransitionResult:
    state: MoneyFlowState
    idempotent: bool


_TRANSITIONS: Mapping[tuple[MoneyFlowState, MoneyFlowEventType], MoneyFlowState] = {
    (MoneyFlowState.DRAFT, MoneyFlowEventType.AUTHORIZE): MoneyFlowState.AUTHORIZED,
    (MoneyFlowState.DRAFT, MoneyFlowEventType.CANCEL): MoneyFlowState.CANCELLED,
    (MoneyFlowState.AUTHORIZED, MoneyFlowEventType.SETTLE): MoneyFlowState.SETTLED,
    (MoneyFlowState.AUTHORIZED, MoneyFlowEventType.CANCEL): MoneyFlowState.CANCELLED,
    (MoneyFlowState.AUTHORIZED, MoneyFlowEventType.FAIL): MoneyFlowState.FAILED,
    (MoneyFlowState.PENDING_SETTLEMENT, MoneyFlowEventType.SETTLE): MoneyFlowState.SETTLED,
    (MoneyFlowState.PENDING_SETTLEMENT, MoneyFlowEventType.FAIL): MoneyFlowState.FAILED,
    (MoneyFlowState.SETTLED, MoneyFlowEventType.REVERSE): MoneyFlowState.REVERSED,
    (MoneyFlowState.SETTLED, MoneyFlowEventType.DISPUTE_OPEN): MoneyFlowState.DISPUTED,
    (MoneyFlowState.DISPUTED, MoneyFlowEventType.DISPUTE_RESOLVE): MoneyFlowState.SETTLED,
}

_IDEMPOTENT_EVENTS: Mapping[MoneyFlowEventType, MoneyFlowState] = {
    MoneyFlowEventType.SETTLE: MoneyFlowState.SETTLED,
    MoneyFlowEventType.REVERSE: MoneyFlowState.REVERSED,
    MoneyFlowEventType.CANCEL: MoneyFlowState.CANCELLED,
}


def apply_transition(
    current_state: MoneyFlowState | None,
    event_type: MoneyFlowEventType,
) -> TransitionResult:
    if current_state is None:
        raise MoneyFlowTransitionError("current_state_required")

    idempotent_state = _IDEMPOTENT_EVENTS.get(event_type)
    if idempotent_state is not None and current_state == idempotent_state:
        return TransitionResult(state=current_state, idempotent=True)

    next_state = _TRANSITIONS.get((current_state, event_type))
    if next_state is None:
        raise MoneyFlowTransitionError(
            f"invalid_transition:{current_state.value}->{event_type.value}"
        )
    return TransitionResult(state=next_state, idempotent=False)


__all__ = ["TransitionResult", "apply_transition"]
