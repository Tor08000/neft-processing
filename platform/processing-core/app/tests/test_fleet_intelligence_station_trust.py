from app.models.fleet_intelligence import StationTrustLevel
from app.services.fleet_intelligence import scores


def test_station_trust_penalties():
    result = scores.compute_station_trust_score(
        scores.StationTrustInputs(
            tx_count=10,
            risk_block_count=1,
            decline_count=2,
            burst_events_count=2,
            outlier_score=40,
            avg_volume_ml=12000,
            network_avg_volume_ml=9000,
        )
    )

    assert result.trust_score < 100
    assert "risk_block_rate" in result.penalties
    assert "burst_events" in result.penalties
    assert "outlier_score" in result.penalties
    assert result.level in {StationTrustLevel.WATCHLIST, StationTrustLevel.BLACKLIST}
