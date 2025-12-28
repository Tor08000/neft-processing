from app.services.money_flow.diff import diff_snapshots
from app.services.money_flow.replay import build_recompute_hash


def test_replay_hash_deterministic():
    payload = {"client_id": "client-1", "billing_period_id": "period-1", "scope": "ALL"}
    assert build_recompute_hash(payload) == build_recompute_hash(payload)


def test_compare_diff_detects_mismatch():
    expected = {"invoice": {"total_with_tax": 100000, "amount_paid": 20000, "amount_due": 80000}}
    actual = {"invoice": {"total_with_tax": 90000, "amount_paid": 20000, "amount_due": 70000}}
    diff = diff_snapshots(expected, actual)
    assert "total_with_tax" in diff.mismatched_totals
    assert diff.recommended_action == "REVIEW_TOTALS"
