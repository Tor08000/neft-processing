from __future__ import annotations

from app.schemas.admin.unified_explain import (
    FleetAssistantBenchmark,
    FleetAssistantBenchmarkBasis,
    FleetAssistantBenchmarkHistory,
    FleetAssistantBenchmarkPeerGroup,
    FleetAssistantBenchmarkPercentile,
)
from app.services.fleet_assistant import benchmarks, peer_groups


def test_percentile_deterministic_sorted_list() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    percentile = benchmarks._percentile_for_value(values, 40.0)

    assert percentile == 0.75


def test_station_trust_inversion() -> None:
    values = [90.0, 80.0, 70.0, 60.0, 50.0]
    percentile = benchmarks._percentile_for_value(values, 50.0, invert_at=100.0)
    p50, p80, p90 = benchmarks._percentile_band(values, invert_at=100.0)

    assert percentile == 1.0
    assert p50 == 70.0
    assert p80 == 60.0
    assert p90 == 50.0


def test_small_sample_returns_insufficient() -> None:
    assert benchmarks._resolve_benchmark_status(9) == "INSUFFICIENT_SAMPLE"


def test_tenant_peer_group_disabled_uses_client() -> None:
    peer_group = peer_groups.resolve_peer_group(
        entity_type="DRIVER",
        tenant_id=11,
        client_id="client-1",
        network_id=None,
        window_days=7,
        as_of=None,
        use_tenant_scope=False,
    )

    assert peer_group.scope == "CLIENT"


def test_benchmark_answer_uses_worse_than_phrase() -> None:
    benchmark = FleetAssistantBenchmark(
        status="OK",
        peer_group=FleetAssistantBenchmarkPeerGroup(scope="CLIENT", client_id="client-1"),
        percentiles=[
            FleetAssistantBenchmarkPercentile(
                metric="driver_behavior_score",
                value=82.0,
                percentile=0.88,
                label="WORSE_THAN_88_PERCENT",
            )
        ],
        n=20,
        basis=FleetAssistantBenchmarkBasis(
            scope="CLIENT",
            window_days=7,
            n=20,
            entity_type="DRIVER",
            as_of="2024-01-01T00:00:00+00:00",
        ),
        history=FleetAssistantBenchmarkHistory(trend_label="DEGRADING", delta_7d=9.2),
    )

    answer = benchmarks.build_benchmark_answer(benchmark)

    assert "хуже, чем 88%" in answer
    assert "вашего парка" in answer
