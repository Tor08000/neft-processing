from app.services.crm.subscription_rules import apply_metric_rules


def test_metric_rules_apply_in_order() -> None:
    usage = {"FUEL_TX_COUNT": 12000}
    rules = [
        {
            "if": {"metric": "FUEL_TX_COUNT", "op": ">", "value": 10000},
            "then": {"set_overage_price_minor": 60, "metric": "FUEL_TX_COUNT"},
        },
        {
            "if": {"metric": "FUEL_TX_COUNT", "op": ">", "value": 11000},
            "then": {"add_base_fee_minor": 2000000},
        },
    ]
    result = apply_metric_rules(usage_by_metric=usage, overage_prices={"FUEL_TX_COUNT": 80}, rules=rules)
    assert result.overage_prices["FUEL_TX_COUNT"] == 60
    assert result.base_fee_adjustments == [2000000]
