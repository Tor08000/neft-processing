from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import requests
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.fuel import FuelStation, FuelStationPrice
from app.models.operation import Operation, OperationStatus
from app.models.station_elasticity import StationElasticity
from app.models.station_margin import StationMarginDay

logger = get_logger(__name__)
settings = get_settings()

_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "commercial_price_policy.json"
_DEFAULT_POLICY = {
    "policy_version": "price-rec-v1",
    "step_up": 0.3,
    "step_down": 0.2,
    "max_delta_per_day": 0.5,
    "margin_target_pct": 0.03,
    "min_volume_7d": 2000.0,
    "min_confidence": 0.4,
    "low_elasticity_abs": 0.5,
    "high_elasticity_threshold": -1.2,
    "high_decline_rate": 0.12,
}


@dataclass
class SignalBundle:
    station_id: str
    product_code: str
    current_price: float
    elasticity_score: float | None
    elasticity_confidence: float
    margin_pct: float | None
    health_status: str
    risk_zone: str
    volume_7d: float
    decline_rate: float


def _policy() -> dict[str, float | str]:
    if _POLICY_PATH.exists():
        try:
            payload = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
            return {**_DEFAULT_POLICY, **payload}
        except Exception:
            logger.exception("commercial.price_recommendations.policy_load_failed")
    return dict(_DEFAULT_POLICY)


def _ch_enabled() -> bool:
    return settings.GEO_ANALYTICS_BACKEND.lower() == "clickhouse"


def _ch_ping() -> bool:
    try:
        response = requests.get(f"{settings.CLICKHOUSE_URL.rstrip('/')}/ping", timeout=5)
        return response.status_code < 400 and response.text.strip() == "Ok."
    except Exception:
        return False


def _ch_exec(query: str) -> None:
    response = requests.post(
        f"{settings.CLICKHOUSE_URL.rstrip('/')}/",
        params={"database": settings.CLICKHOUSE_DB, "query": query},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)


def _ch_query(query: str) -> list[dict]:
    response = requests.post(
        f"{settings.CLICKHOUSE_URL.rstrip('/')}/",
        params={"database": settings.CLICKHOUSE_DB, "query": f"{query} FORMAT JSONEachRow"},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _ch_insert(rows: list[dict]) -> None:
    if not rows:
        return
    payload = "\n".join(json.dumps(item, separators=(",", ":")) for item in rows) + "\n"
    response = requests.post(
        f"{settings.CLICKHOUSE_URL.rstrip('/')}/",
        params={"database": settings.CLICKHOUSE_DB, "query": "INSERT INTO neft_geo.fact_price_recommendations FORMAT JSONEachRow"},
        data=payload.encode("utf-8"),
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)


def ensure_price_recommendations_table() -> None:
    if not _ch_enabled() or not _ch_ping():
        return
    _ch_exec(
        """
        CREATE TABLE IF NOT EXISTS neft_geo.fact_price_recommendations (
            recommendation_id String,
            day Date MATERIALIZED toDate(created_at),
            created_at DateTime,
            station_id UInt64,
            product_code LowCardinality(String),
            current_price Float64,
            recommended_price Float64,
            delta_price Float64,
            action LowCardinality(String),
            confidence Float64,
            reasons Array(LowCardinality(String)),
            expected_volume_change_pct Nullable(Float64),
            expected_margin_change Nullable(Float64),
            policy_version LowCardinality(String),
            status LowCardinality(String),
            meta String
        ) ENGINE = MergeTree
        PARTITION BY toYYYYMM(created_at)
        ORDER BY (created_at, station_id, product_code)
        """
    )


def _quantize(value: float) -> float:
    return round(value, 3)


def _decision(signal: SignalBundle, policy: dict[str, float | str]) -> dict[str, object]:
    reasons: list[str] = []
    action = "HOLD"
    delta = 0.0
    confidence = min(max(signal.elasticity_confidence, 0.0), 1.0)

    if signal.health_status.upper() == "OFFLINE":
        return {"action": "REVIEW_REQUIRED", "delta": 0.0, "confidence": 0.95, "reasons": ["HEALTH_OFFLINE"]}
    if signal.risk_zone.upper() == "RED":
        return {"action": "REVIEW_REQUIRED", "delta": 0.0, "confidence": 0.9, "reasons": ["RISK_RED"]}
    if signal.elasticity_confidence < float(policy["min_confidence"]):
        return {"action": "HOLD", "delta": 0.0, "confidence": confidence, "reasons": ["LOW_CONFIDENCE"]}
    if signal.volume_7d < float(policy["min_volume_7d"]):
        return {"action": "HOLD", "delta": 0.0, "confidence": confidence, "reasons": ["LOW_VOLUME"]}

    e = signal.elasticity_score if signal.elasticity_score is not None else 0.0
    margin = signal.margin_pct if signal.margin_pct is not None else 0.0

    if abs(e) < float(policy["low_elasticity_abs"]) and margin < float(policy["margin_target_pct"]):
        action = "INCREASE_PRICE"
        delta = min(float(policy["step_up"]), float(policy["max_delta_per_day"]))
        reasons = ["LOW_ELASTICITY", "LOW_MARGIN"]
    elif e <= float(policy["high_elasticity_threshold"]) and signal.decline_rate >= float(policy["high_decline_rate"]):
        action = "DECREASE_PRICE"
        delta = -min(float(policy["step_down"]), float(policy["max_delta_per_day"]))
        reasons = ["HIGH_ELASTICITY", "HIGH_DECLINE"]
    else:
        reasons = ["MARGIN_STABLE"]

    return {"action": action, "delta": delta, "confidence": confidence, "reasons": reasons}


def _recommendation_id(station_id: str, product_code: str, created_day: date, policy_version: str) -> str:
    digest = hashlib.sha1(f"{station_id}:{product_code}:{created_day.isoformat()}:{policy_version}".encode("utf-8")).hexdigest()
    return digest[:24]


def _load_signals(db: Session, window_days: int) -> list[SignalBundle]:
    target_day = datetime.now(tz=timezone.utc).date() - timedelta(days=1)
    margin_rows = db.query(StationMarginDay).filter(StationMarginDay.day == target_day).all()
    margin_map = {str(row.station_id): row for row in margin_rows}

    now = datetime.now(tz=timezone.utc)
    start_7d = now - timedelta(days=7)
    start_14d = now - timedelta(days=14)

    vol_rows = (
        db.query(
            Operation.fuel_station_id.label("station_id"),
            func.coalesce(Operation.product_code, "").label("product_code"),
            func.sum(func.coalesce(Operation.quantity, 1)).label("volume_7d"),
        )
        .filter(
            Operation.created_at >= start_7d,
            Operation.fuel_station_id.isnot(None),
            Operation.status.in_([OperationStatus.CAPTURED, OperationStatus.COMPLETED]),
        )
        .group_by(Operation.fuel_station_id, func.coalesce(Operation.product_code, ""))
        .all()
    )

    prev_rows = (
        db.query(
            Operation.fuel_station_id.label("station_id"),
            func.coalesce(Operation.product_code, "").label("product_code"),
            func.sum(func.coalesce(Operation.quantity, 1)).label("volume_prev_7d"),
        )
        .filter(
            Operation.created_at >= start_14d,
            Operation.created_at < start_7d,
            Operation.fuel_station_id.isnot(None),
            Operation.status.in_([OperationStatus.CAPTURED, OperationStatus.COMPLETED]),
        )
        .group_by(Operation.fuel_station_id, func.coalesce(Operation.product_code, ""))
        .all()
    )

    vol_map = {(str(r.station_id), str(r.product_code or "")): float(r.volume_7d or 0) for r in vol_rows}
    prev_map = {(str(r.station_id), str(r.product_code or "")): float(r.volume_prev_7d or 0) for r in prev_rows}

    elasticity_rows = db.query(StationElasticity).filter(StationElasticity.window_days == window_days).all()
    elasticity_map = {(str(r.station_id), str(r.product_code or "")): r for r in elasticity_rows}

    prices = (
        db.query(FuelStationPrice)
        .filter(
            FuelStationPrice.status == "ACTIVE",
            or_(FuelStationPrice.valid_to.is_(None), FuelStationPrice.valid_to >= now),
        )
        .order_by(FuelStationPrice.station_id, FuelStationPrice.product_code, FuelStationPrice.valid_from.desc())
        .all()
    )
    latest_price: dict[tuple[str, str], FuelStationPrice] = {}
    for price in prices:
        key = (str(price.station_id), str(price.product_code or ""))
        latest_price.setdefault(key, price)

    stations = {str(st.id): st for st in db.query(FuelStation).all()}
    keys = set(vol_map) | set(elasticity_map) | set(latest_price)
    bundles: list[SignalBundle] = []
    for key in keys:
        station_id, product_code = key
        station = stations.get(station_id)
        if not station:
            continue
        price = latest_price.get(key)
        if not price:
            continue
        margin_row = margin_map.get(station_id)
        revenue = float(getattr(margin_row, "revenue_sum", 0) or 0)
        cost = float(getattr(margin_row, "cost_sum", 0) or 0)
        margin_pct = ((revenue - cost) / revenue) if revenue > 0 else None
        elasticity = elasticity_map.get(key) or elasticity_map.get((station_id, ""))
        vol = vol_map.get(key, vol_map.get((station_id, ""), 0.0))
        prev = prev_map.get(key, prev_map.get((station_id, ""), 0.0))
        decline_rate = max(0.0, (prev - vol) / prev) if prev > 0 else 0.0
        bundles.append(
            SignalBundle(
                station_id=station_id,
                product_code=product_code,
                current_price=float(price.price),
                elasticity_score=float(elasticity.elasticity_score) if elasticity else None,
                elasticity_confidence=float(elasticity.confidence_score) if elasticity else 0.0,
                margin_pct=margin_pct,
                health_status=str(station.health_status or "UNKNOWN"),
                risk_zone=str(station.risk_zone or "UNKNOWN"),
                volume_7d=vol,
                decline_rate=decline_rate,
            )
        )
    return bundles


def build_price_recommendations(db: Session, window_days: int = 90) -> dict[str, object]:
    policy = _policy()
    created_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
    signals = _load_signals(db, window_days=window_days)
    rows: list[dict] = []
    for signal in signals:
        decision = _decision(signal, policy)
        delta = float(decision["delta"])
        new_price = _quantize(max(0.0, signal.current_price + delta))
        delta_pct = (delta / signal.current_price) if signal.current_price > 0 else 0.0
        expected_volume_change_pct = None
        if signal.elasticity_score is not None:
            expected_volume_change_pct = _quantize(signal.elasticity_score * delta_pct)

        expected_margin_change = None
        reasons = list(decision["reasons"])
        if signal.margin_pct is None:
            reasons.append("COST_UNKNOWN")

        rec_id = _recommendation_id(signal.station_id, signal.product_code, created_at.date(), str(policy["policy_version"]))
        rows.append(
            {
                "recommendation_id": rec_id,
                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "station_id": int(signal.station_id),
                "product_code": signal.product_code,
                "current_price": _quantize(signal.current_price),
                "recommended_price": new_price,
                "delta_price": _quantize(delta),
                "action": str(decision["action"]).replace("_PRICE", ""),
                "confidence": _quantize(float(decision["confidence"])),
                "reasons": reasons,
                "expected_volume_change_pct": expected_volume_change_pct,
                "expected_margin_change": expected_margin_change,
                "policy_version": str(policy["policy_version"]),
                "status": "DRAFT",
                "meta": json.dumps({
                    "health_status": signal.health_status,
                    "risk_zone": signal.risk_zone,
                    "decline_rate": signal.decline_rate,
                    "volume_7d": signal.volume_7d,
                    "window_days": window_days,
                }, separators=(",", ":")),
            }
        )

    if _ch_enabled() and _ch_ping():
        ensure_price_recommendations_table()
        policy_version = str(policy["policy_version"])
        _ch_exec(
            f"ALTER TABLE neft_geo.fact_price_recommendations DELETE WHERE day = toDate('{created_at.date().isoformat()}') AND policy_version = '{policy_version}'"
        )
        _ch_insert(rows)
    return {"created_at": created_at.isoformat(), "rows": len(rows), "policy_version": policy["policy_version"]}


def list_price_recommendations(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    status: str | None,
    action: str | None,
    min_confidence: float | None,
    risk_zone: str | None,
    health_status: str | None,
    limit: int,
) -> list[dict]:
    if not _ch_enabled() or not _ch_ping():
        return []

    filters = [f"day >= toDate('{date_from.isoformat()}')", f"day <= toDate('{date_to.isoformat()}')"]
    if status:
        filters.append(f"status = '{status}'")
    if action:
        filters.append(f"action = '{action}'")
    if min_confidence is not None:
        filters.append(f"confidence >= {float(min_confidence)}")

    where = " AND ".join(filters)
    rows = _ch_query(
        f"""
        SELECT recommendation_id, created_at, station_id, product_code, current_price, recommended_price,
               delta_price, action, confidence, reasons, expected_volume_change_pct, expected_margin_change,
               policy_version, status, meta
        FROM neft_geo.fact_price_recommendations
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT {int(limit)}
        """
    )

    station_ids = [str(row["station_id"]) for row in rows]
    stations = {}
    if station_ids:
        q = db.query(FuelStation).filter(FuelStation.id.in_(station_ids))
        if risk_zone:
            q = q.filter(FuelStation.risk_zone == risk_zone)
        if health_status:
            q = q.filter(FuelStation.health_status == health_status)
        stations = {str(s.id): s for s in q.all()}

    output: list[dict] = []
    for row in rows:
        station = stations.get(str(row["station_id"]))
        if (risk_zone or health_status) and not station:
            continue
        meta = json.loads(row.get("meta") or "{}")
        output.append(
            {
                "id": row["recommendation_id"],
                "created_at": row["created_at"],
                "station_id": str(row["station_id"]),
                "station_name": station.name if station else None,
                "station_address": station.city if station else None,
                "risk_zone": station.risk_zone if station else meta.get("risk_zone"),
                "health_status": station.health_status if station else meta.get("health_status"),
                "product_code": row.get("product_code") or "",
                "current_price": float(row.get("current_price") or 0),
                "recommended_price": float(row.get("recommended_price") or 0),
                "delta_price": float(row.get("delta_price") or 0),
                "action": row.get("action") or "HOLD",
                "confidence": float(row.get("confidence") or 0),
                "reasons": list(row.get("reasons") or []),
                "expected_volume_change_pct": row.get("expected_volume_change_pct"),
                "expected_margin_change": row.get("expected_margin_change"),
                "policy_version": row.get("policy_version") or "",
                "status": row.get("status") or "DRAFT",
            }
        )
    return output


def get_station_price_recommendations(db: Session, station_id: str, *, limit: int = 50) -> list[dict]:
    return [row for row in list_price_recommendations(
        db,
        date_from=datetime.now(tz=timezone.utc).date() - timedelta(days=30),
        date_to=datetime.now(tz=timezone.utc).date(),
        status=None,
        action=None,
        min_confidence=None,
        risk_zone=None,
        health_status=None,
        limit=limit,
    ) if row["station_id"] == station_id]


def update_recommendation_status(recommendation_id: str, status: str) -> bool:
    if not _ch_enabled() or not _ch_ping():
        return False
    ensure_price_recommendations_table()
    _ch_exec(
        "ALTER TABLE neft_geo.fact_price_recommendations "
        f"UPDATE status = '{status}' WHERE recommendation_id = '{recommendation_id}'"
    )
    return True
