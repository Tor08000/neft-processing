from app.services.fleet_intelligence import scores


def test_driver_score_deterministic():
    inputs = scores.DriverScoreInputs(
        off_route_fuel_count=2,
        night_fuel_tx_count=1,
        route_deviation_count=0,
        risk_block_count=1,
        review_required_count=1,
        tx_count=5,
    )
    first = scores.compute_driver_behavior_score(inputs)
    second = scores.compute_driver_behavior_score(inputs)

    assert first.score == second.score
    assert first.level == second.level
    assert first.contributions == second.contributions
