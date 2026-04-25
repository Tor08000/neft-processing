from datetime import datetime, timezone
from uuid import uuid4

from app.services.decision import DecisionAction, DecisionContext, DecisionEngine
from app.services.decision.engine import _normalize_actor_roles


def test_decision_context_to_payload_normalizes_set_uuid_and_datetime():
    first_id = uuid4()
    second_id = uuid4()
    context = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="ADMIN",
        actor_id="admin-1",
        action=DecisionAction.DOCUMENT_FINALIZE,
        amount=0,
        history={"labels": {"finalize", "docs"}},
        metadata={
            "actor_roles": {"ADMIN_FINANCE", "ADMIN"},
            "subject_id": first_id,
            "issued_at": datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc),
            "related_ids": {first_id, second_id},
        },
    )

    payload = context.to_payload()

    assert payload["history"]["labels"] == ["docs", "finalize"]
    assert payload["metadata"]["actor_roles"] == ["ADMIN", "ADMIN_FINANCE"]
    assert payload["metadata"]["subject_id"] == str(first_id)
    assert payload["metadata"]["issued_at"] == "2024-01-03T10:00:00+00:00"
    assert payload["metadata"]["related_ids"] == sorted([str(first_id), str(second_id)])


def test_decision_engine_evaluate_accepts_set_actor_roles_in_metadata():
    context = DecisionContext(
        tenant_id=1,
        client_id="client-1",
        actor_type="ADMIN",
        actor_id="admin-1",
        action=DecisionAction.DOCUMENT_FINALIZE,
        amount=0,
        history={"labels": {"finalize", "docs"}},
        metadata={
            "actor_roles": {"ADMIN_FINANCE", "ADMIN"},
            "actor_email": "admin@neft.local",
            "issued_at": datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc),
        },
    )

    result = DecisionEngine().evaluate(context)

    assert result.explain["inputs"]["metadata"]["actor_roles"] == ["ADMIN", "ADMIN_FINANCE"]
    assert result.explain["inputs"]["history"]["labels"] == ["docs", "finalize"]
    assert result.explain["inputs"]["metadata"]["issued_at"] == "2024-01-03T10:00:00+00:00"


def test_normalize_actor_roles_returns_sorted_list_for_sets():
    assert _normalize_actor_roles({"ADMIN_FINANCE", "ADMIN"}) == ["ADMIN", "ADMIN_FINANCE"]
    assert _normalize_actor_roles("ADMIN") == ["ADMIN"]
    assert _normalize_actor_roles(None) is None
