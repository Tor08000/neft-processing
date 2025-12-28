from app.services.money_flow.snapshots import build_snapshot_hash, evaluate_snapshot_invariants


def test_snapshot_hash_deterministic():
    payload_a = {
        "invoice": {"total_with_tax": 100000, "amount_paid": 20000, "amount_due": 80000},
        "ledger": {"balanced": True},
    }
    payload_b = {
        "ledger": {"balanced": True},
        "invoice": {"amount_due": 80000, "amount_paid": 20000, "total_with_tax": 100000},
    }

    assert build_snapshot_hash(payload_a) == build_snapshot_hash(payload_b)


def test_partial_payment_invariants_pass():
    payload = {
        "invoice": {"total_with_tax": 100000, "amount_paid": 20000, "amount_due": 80000, "amount_refunded": 0}
    }
    assert evaluate_snapshot_invariants(payload) == []


def test_refund_exceeds_paid_violation():
    payload = {
        "invoice": {"total_with_tax": 100000, "amount_paid": 20000, "amount_due": 80000, "amount_refunded": 30000}
    }
    violations = evaluate_snapshot_invariants(payload)
    assert "refund_exceeds_paid" in violations
