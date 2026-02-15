from app.services.event_outbox import build_idempotency_key, compute_backoff


def test_build_idempotency_key_is_stable() -> None:
    assert (
        build_idempotency_key(aggregate_type="card", aggregate_id="card-1", event_type="card.created")
        == "card:card-1:card.created"
    )


def test_compute_backoff_uses_configured_schedule() -> None:
    assert compute_backoff(1) == 1
    assert compute_backoff(2) == 5
    assert compute_backoff(3) == 30
    assert compute_backoff(4) == 120
    assert compute_backoff(5) == 300
    assert compute_backoff(99) == 300
