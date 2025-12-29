from app.services.fleet_intelligence import scores


def test_vehicle_efficiency_baseline_delta():
    result = scores.compute_vehicle_efficiency_score(
        window_days=7,
        daily_values=[300.0, 320.0, 310.0],
        baseline_values=[280.0, 290.0, 300.0],
    )

    assert result.baseline_ml_per_100km == 290.0
    assert result.actual_ml_per_100km == 310.0
    assert round(result.delta_pct, 3) == round((310.0 - 290.0) / 290.0, 3)
    assert result.efficiency_score is not None
