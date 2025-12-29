from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models.crm import CRMClient
from app.schemas.admin.unified_explain import (
    FleetAssistantBenchmark,
    FleetAssistantBenchmarkBasis,
    FleetAssistantBenchmarkHistory,
    FleetAssistantBenchmarkPeerGroup,
    FleetAssistantBenchmarkPercentile,
    UnifiedExplainResponse,
)
from app.services.fleet_assistant.peer_groups import resolve_peer_group
from app.services.fleet_intelligence import repository


MIN_SAMPLE_SIZE = 10


@dataclass(frozen=True)
class BenchmarkResult:
    benchmark: FleetAssistantBenchmark
    answer: str | None


def build_benchmark_response(
    explain: UnifiedExplainResponse,
    *,
    db: Session | None,
) -> BenchmarkResult | None:
    if not db:
        return None
    entity_type = _resolve_entity_type(explain)
    if not entity_type:
        return None
    subject = explain.subject
    if not subject.client_id:
        return None
    client = db.get(CRMClient, subject.client_id)
    tenant_id = client.tenant_id if client else None
    if tenant_id is None:
        return None
    benchmark = _build_benchmark(db, explain, entity_type=entity_type, tenant_id=tenant_id)
    if not benchmark:
        return None
    answer = build_benchmark_answer(benchmark)
    return BenchmarkResult(benchmark=benchmark, answer=answer)


def build_benchmark_answer(benchmark: FleetAssistantBenchmark) -> str | None:
    if benchmark.status != "OK":
        return _format_history_answer(benchmark)
    percentile_entry = _find_primary_percentile(benchmark)
    if not percentile_entry or percentile_entry.percentile is None:
        return _format_history_answer(benchmark)
    basis = benchmark.basis
    scope = basis.scope
    window_days = basis.window_days
    entity_type = basis.entity_type
    worse_pct = int(round(percentile_entry.percentile * 100))
    scope_phrase = "вашего парка" if scope == "CLIENT" else "в рамках вашего тенанта"

    if entity_type == "DRIVER":
        return (
            f"Этот водитель хуже, чем {worse_pct}% водителей {scope_phrase} "
            f"за последние {window_days} дней."
        )
    if entity_type == "VEHICLE":
        return (
            f"Перерасход хуже, чем у {worse_pct}% ТС {scope_phrase} "
            f"за последние {window_days} дней."
        )
    if entity_type == "STATION":
        lower_pct = max(0, 100 - worse_pct)
        network_id = benchmark.peer_group.network_id
        network_phrase = f"сети {network_id}" if network_id else "вашего тенанта"
        return (
            f"Эта станция в нижних {lower_pct}% по доверенности среди станций {network_phrase} "
            f"за последние {window_days} дней."
        )
    return None


def _build_benchmark(
    db: Session,
    explain: UnifiedExplainResponse,
    *,
    entity_type: str,
    tenant_id: int | None,
) -> FleetAssistantBenchmark | None:
    subject = explain.subject
    if entity_type == "DRIVER" and subject.driver_id:
        window_days = 7
        current = repository.get_latest_driver_score(
            db,
            tenant_id=tenant_id,
            client_id=subject.client_id,
            driver_id=subject.driver_id,
            window_days=window_days,
        )
        if not current:
            return None
        peer_group = resolve_peer_group(
            entity_type=entity_type,
            tenant_id=tenant_id,
            client_id=subject.client_id,
            network_id=None,
            window_days=window_days,
            as_of=current.computed_at,
            use_tenant_scope=settings.FLEET_BENCHMARK_USE_TENANT,
        )
        if peer_group.scope == "TENANT":
            peers = repository.list_latest_driver_scores_by_tenant(
                db,
                tenant_id=tenant_id,
                window_days=window_days,
                as_of=current.computed_at,
            )
        else:
            peers = repository.list_latest_driver_scores_by_client(
                db,
                client_id=subject.client_id,
                window_days=window_days,
                as_of=current.computed_at,
            )
        driver_scores = [float(score.score) for score in peers if score.score is not None]
        percentiles = _build_percentiles(
            metric="driver_behavior_score",
            values=driver_scores,
            current_value=float(current.score) if current.score is not None else None,
        )
        history = _build_history(explain, entity_type=entity_type)
        return _finalize_benchmark(
            entity_type=entity_type,
            peer_group=peer_group,
            as_of=current.computed_at,
            percentiles=percentiles,
            history=history,
            primary_values=driver_scores,
        )
    if entity_type == "VEHICLE" and subject.vehicle_id:
        window_days = 7
        current = repository.get_latest_vehicle_score(
            db,
            tenant_id=tenant_id,
            client_id=subject.client_id,
            vehicle_id=subject.vehicle_id,
            window_days=window_days,
        )
        if not current:
            return None
        peer_group = resolve_peer_group(
            entity_type=entity_type,
            tenant_id=tenant_id,
            client_id=subject.client_id,
            network_id=None,
            window_days=window_days,
            as_of=current.computed_at,
            use_tenant_scope=settings.FLEET_BENCHMARK_USE_TENANT,
        )
        if peer_group.scope == "TENANT":
            peers = repository.list_latest_vehicle_scores_by_tenant(
                db,
                tenant_id=tenant_id,
                window_days=window_days,
                as_of=current.computed_at,
            )
        else:
            peers = repository.list_latest_vehicle_scores_by_client(
                db,
                client_id=subject.client_id,
                window_days=window_days,
                as_of=current.computed_at,
            )
        peers = [score for score in peers if score.actual_ml_per_100km is not None]
        delta_values = [float(score.delta_pct) for score in peers if score.delta_pct is not None]
        fuel_values = [float(score.actual_ml_per_100km) for score in peers if score.actual_ml_per_100km is not None]
        percentiles = []
        percentiles.extend(
            _build_percentiles(
                metric="vehicle_efficiency_delta_pct",
                values=delta_values,
                current_value=float(current.delta_pct) if current.delta_pct is not None else None,
            )
        )
        percentiles.extend(
            _build_percentiles(
                metric="fuel_per_100km",
                values=fuel_values,
                current_value=float(current.actual_ml_per_100km) if current.actual_ml_per_100km is not None else None,
            )
        )
        history = _build_history(explain, entity_type=entity_type)
        return _finalize_benchmark(
            entity_type=entity_type,
            peer_group=peer_group,
            as_of=current.computed_at,
            percentiles=percentiles,
            history=history,
            primary_values=delta_values,
        )
    if entity_type == "STATION" and subject.station_id:
        window_days = 30
        current = repository.get_latest_station_score(
            db,
            tenant_id=tenant_id,
            station_id=subject.station_id,
            window_days=window_days,
        )
        if not current:
            return None
        peer_group = resolve_peer_group(
            entity_type=entity_type,
            tenant_id=tenant_id,
            client_id=subject.client_id,
            network_id=str(current.network_id) if current.network_id else None,
            window_days=window_days,
            as_of=current.computed_at,
            use_tenant_scope=settings.FLEET_BENCHMARK_USE_TENANT,
        )
        peers = repository.list_latest_station_scores_by_tenant_network(
            db,
            tenant_id=tenant_id,
            window_days=window_days,
            network_id=str(current.network_id) if current.network_id else None,
            as_of=current.computed_at,
        )
        trust_values = [float(score.trust_score) for score in peers if score.trust_score is not None]
        percentiles = _build_percentiles(
            metric="station_trust_score",
            values=trust_values,
            current_value=float(current.trust_score) if current.trust_score is not None else None,
            invert_at=100.0,
        )
        risk_percentiles = _build_station_risk_block_percentiles(
            db,
            tenant_id=tenant_id,
            current_station_id=str(subject.station_id),
            peer_group=peer_group,
            as_of=current.computed_at.date(),
            window_days=window_days,
        )
        percentiles.extend(risk_percentiles)
        history = _build_history(explain, entity_type=entity_type)
        return _finalize_benchmark(
            entity_type=entity_type,
            peer_group=peer_group,
            as_of=current.computed_at,
            percentiles=percentiles,
            history=history,
            primary_values=trust_values,
        )
    return None


def _build_station_risk_block_percentiles(
    db: Session,
    *,
    tenant_id: int,
    current_station_id: str,
    peer_group,
    as_of: date,
    window_days: int,
) -> list[FleetAssistantBenchmarkPercentile]:
    start_day = as_of - timedelta(days=window_days - 1)
    rates_by_station = repository.list_station_risk_block_rates(
        db,
        tenant_id=tenant_id,
        start_day=start_day,
        end_day=as_of,
        network_id=peer_group.network_id,
    )
    current_rate = rates_by_station.get(current_station_id)
    rates = list(rates_by_station.values())
    if current_rate is None or not rates:
        return []
    return _build_percentiles(
        metric="risk_block_rate",
        values=rates,
        current_value=current_rate,
    )


def _finalize_benchmark(
    *,
    entity_type: str,
    peer_group,
    as_of: datetime,
    percentiles: list[FleetAssistantBenchmarkPercentile],
    history: FleetAssistantBenchmarkHistory | None,
    primary_values: list[float],
) -> FleetAssistantBenchmark:
    n = len(primary_values)
    status = _resolve_benchmark_status(n)
    if status != "OK":
        percentiles = []
    basis = FleetAssistantBenchmarkBasis(
        scope=peer_group.scope,
        window_days=peer_group.window_days,
        n=n,
        entity_type=entity_type,
        as_of=as_of.isoformat(),
    )
    peer_group_payload = FleetAssistantBenchmarkPeerGroup(
        scope=peer_group.scope,
        client_id=peer_group.client_id,
        tenant_id=peer_group.tenant_id,
        network_id=peer_group.network_id,
    )
    return FleetAssistantBenchmark(
        status=status,
        peer_group=peer_group_payload,
        percentiles=percentiles,
        n=n,
        basis=basis,
        history=history,
    )


def _resolve_benchmark_status(n: int) -> str:
    return "OK" if n >= MIN_SAMPLE_SIZE else "INSUFFICIENT_SAMPLE"


def _build_percentiles(
    *,
    metric: str,
    values: list[float],
    current_value: float | None,
    invert_at: float | None = None,
) -> list[FleetAssistantBenchmarkPercentile]:
    if current_value is None or not values:
        return []
    percentile = _percentile_for_value(values, current_value, invert_at=invert_at)
    if percentile is None:
        return []
    label = f"WORSE_THAN_{int(round(percentile * 100))}_PERCENT"
    p50, p80, p90 = _percentile_band(values, invert_at=invert_at)
    return [
        FleetAssistantBenchmarkPercentile(
            metric=metric,
            value=current_value,
            percentile=percentile,
            label=label,
        ),
        FleetAssistantBenchmarkPercentile(metric=metric, p50=p50, p80=p80, p90=p90),
    ]


def _percentile_for_value(
    values: list[float],
    value: float,
    *,
    invert_at: float | None = None,
) -> float | None:
    normalized = _normalize_values(values, invert_at=invert_at)
    if not normalized:
        return None
    normalized_value = _normalize_value(value, invert_at=invert_at)
    normalized.sort()
    if len(normalized) == 1:
        return 0.0
    rank_index = max(0, bisect_right(normalized, normalized_value) - 1)
    return rank_index / (len(normalized) - 1)


def _percentile_band(
    values: list[float],
    *,
    invert_at: float | None = None,
) -> tuple[float | None, float | None, float | None]:
    normalized = _normalize_values(values, invert_at=invert_at)
    if not normalized:
        return None, None, None
    normalized.sort()
    p50 = _value_at_percentile(normalized, 0.5)
    p80 = _value_at_percentile(normalized, 0.8)
    p90 = _value_at_percentile(normalized, 0.9)
    if invert_at is not None:
        return (
            _denormalize_value(p50, invert_at=invert_at),
            _denormalize_value(p80, invert_at=invert_at),
            _denormalize_value(p90, invert_at=invert_at),
        )
    return p50, p80, p90


def _value_at_percentile(values: list[float], percentile: float) -> float:
    index = int(round(percentile * (len(values) - 1)))
    return values[index]


def _normalize_values(values: list[float], *, invert_at: float | None) -> list[float]:
    return [_normalize_value(value, invert_at=invert_at) for value in values]


def _normalize_value(value: float, *, invert_at: float | None) -> float:
    return invert_at - value if invert_at is not None else value


def _denormalize_value(value: float | None, *, invert_at: float) -> float | None:
    if value is None:
        return None
    return invert_at - value


def _build_history(explain: UnifiedExplainResponse, *, entity_type: str) -> FleetAssistantBenchmarkHistory | None:
    fleet_trends = explain.sections.get("fleet_trends")
    if not isinstance(fleet_trends, dict):
        return None
    key = {"DRIVER": "driver", "VEHICLE": "vehicle", "STATION": "station"}.get(entity_type)
    if not key:
        return None
    payload = fleet_trends.get(key)
    if not isinstance(payload, dict):
        return None
    return FleetAssistantBenchmarkHistory(
        trend_label=payload.get("label"),
        delta_7d=payload.get("delta"),
    )


def _format_history_answer(benchmark: FleetAssistantBenchmark) -> str | None:
    history = benchmark.history
    if not history:
        return "Недостаточно данных для сравнения с другими участниками."
    delta = history.delta_7d
    delta_text = f", дельта {delta:.1f}" if isinstance(delta, (int, float)) else ""
    return f"Недостаточно данных для сравнения с другими. Тренд: {history.trend_label}{delta_text}."


def _find_primary_percentile(
    benchmark: FleetAssistantBenchmark,
) -> FleetAssistantBenchmarkPercentile | None:
    primary_metric = {
        "DRIVER": "driver_behavior_score",
        "VEHICLE": "vehicle_efficiency_delta_pct",
        "STATION": "station_trust_score",
    }.get(benchmark.basis.entity_type)
    if not primary_metric:
        return None
    for item in benchmark.percentiles:
        if item.metric == primary_metric and item.percentile is not None:
            return item
    return None


def _resolve_entity_type(explain: UnifiedExplainResponse) -> str | None:
    subject = explain.subject
    if subject.driver_id:
        return "DRIVER"
    if subject.station_id:
        return "STATION"
    if subject.vehicle_id:
        return "VEHICLE"
    return None


__all__ = ["BenchmarkResult", "build_benchmark_answer", "build_benchmark_response"]
