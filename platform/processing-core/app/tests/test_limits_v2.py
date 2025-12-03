from app.models.limit_rule import LimitRule
from app.services.limits import CheckAndReserveRequest
from app.services.limits_engine import evaluate_limits, select_best_rule


def test_limits_phase_auth_vs_capture():
    rules = [
        LimitRule(id=1, phase="AUTH", daily_limit=1_000, limit_per_tx=500),
        LimitRule(id=2, phase="CAPTURE", daily_limit=2_000, limit_per_tx=800),
    ]

    auth_req = CheckAndReserveRequest(amount=100, phase="AUTH")
    capture_req = CheckAndReserveRequest(amount=100, phase="CAPTURE")

    assert select_best_rule(auth_req, rules).id == 1
    assert select_best_rule(capture_req, rules).id == 2


def test_limits_filter_by_product_category_mcc_tx_type():
    diesel_rule = LimitRule(
        id=3,
        product_category="DIESEL",
        mcc=None,
        tx_type="FUEL",
        daily_limit=500,
        limit_per_tx=200,
    )

    diesel_req = CheckAndReserveRequest(amount=100, product_category="DIESEL", tx_type="FUEL")
    gasoline_req = CheckAndReserveRequest(amount=100, product_category="GASOLINE", tx_type="FUEL")
    other_req = CheckAndReserveRequest(amount=100, mcc="1234", tx_type="OTHER")

    assert select_best_rule(diesel_req, [diesel_rule]).id == 3
    assert select_best_rule(gasoline_req, [diesel_rule]) is None
    assert select_best_rule(other_req, [diesel_rule]) is None


def test_limits_specificity_with_groups():
    group_rule = LimitRule(
        id=4,
        client_group_id="G1",
        daily_limit=1_000,
        limit_per_tx=500,
    )
    direct_rule = LimitRule(
        id=5,
        client_id="c1",
        daily_limit=1_000,
        limit_per_tx=500,
    )

    request = CheckAndReserveRequest(
        amount=100, client_id="c1", client_group_id="G1"
    )

    assert select_best_rule(request, [group_rule, direct_rule]).id == 5


def test_limits_v2_backward_compatibility():
    simple_rule = LimitRule(id=6, daily_limit=150, limit_per_tx=100)
    request = CheckAndReserveRequest(amount=50)

    result = evaluate_limits(request, [simple_rule], used_today=20)

    assert result["approved"] is True
    assert result["applied_rule_id"] == 6
