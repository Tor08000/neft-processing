from __future__ import annotations

import pytest

from app.models.edo import EdoDocumentStatus
from app.services.edo.state_machine import EdoStateMachine, TransitionError


@pytest.mark.unit
def test_state_machine_allows_expected_transitions() -> None:
    assert EdoStateMachine.can_transition(EdoDocumentStatus.DRAFT, EdoDocumentStatus.QUEUED)
    assert EdoStateMachine.can_transition(EdoDocumentStatus.QUEUED, EdoDocumentStatus.SENDING)
    assert EdoStateMachine.can_transition(EdoDocumentStatus.SENDING, EdoDocumentStatus.SENT)
    assert EdoStateMachine.can_transition(EdoDocumentStatus.SENDING, EdoDocumentStatus.FAILED)
    assert EdoStateMachine.can_transition(EdoDocumentStatus.SENT, EdoDocumentStatus.DELIVERED)
    assert EdoStateMachine.can_transition(EdoDocumentStatus.DELIVERED, EdoDocumentStatus.SIGNED)
    assert EdoStateMachine.can_transition(EdoDocumentStatus.FAILED, EdoDocumentStatus.QUEUED)


@pytest.mark.unit
def test_state_machine_blocks_unknown_transition() -> None:
    with pytest.raises(TransitionError):
        EdoStateMachine.assert_transition(EdoDocumentStatus.SENT, EdoDocumentStatus.DRAFT)
