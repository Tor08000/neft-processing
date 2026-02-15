from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import requests
from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.fuel import (
    CommercialRecommendationAction,
    FuelStation,
    FuelStationPrice,
    FuelStationPriceSource,
    FuelStationPriceStatus,
    FuelStationStatus,
)
from app.models.operation import Operation, OperationStatus
from app.models.station_elasticity import StationElasticity
from app.models.station_margin import StationMarginDay
from app.services.fuel_prices import write_price_audit

logger = get_logger(__name__)
settings = get_settings()

_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "commercial_price_policy.json"
_DEFAULT_POLICY = {
    "version": "v1",
    "step_up": 0.3,
    "step_down": 0.2,
    "max_delta_per_day": 0.5,
    "target_margin_pct": 0.03,
    "min_volume_7d": 50.0,
    "min_revenue_7d": 50000.0,
    "elasticity_low_abs": 0.5,
    "elasticity_high_abs": 1.2,
    "high_decline_rate": 0.12,
    "min_confidence_to_change": 0.6,
    "guardrail_risk_zone_red": True,
    "guardrail_health_offline": True,
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
    revenue_7d: float
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
            rec_id String,
            created_at DateTime,
            day Date MATERIALIZED toDate(created_at),
            station_id UInt64,
            product_code LowCardinality(String),
            current_price Float64,
            recommended_price Float64,
            delta_price Float64,
            action LowCardinality(String),
            confidence Float64,
            reasons Array(LowCardinality(String)),
            expected_volume_change_pct Float64,
            expected_margin_change Float64,
            policy_version LowCardinality(String),
            status LowCardinality(String),
            decided_at Nullable(DateTime),
            decided_by Nullable(String),
            meta String
        ) ENGINE = MergeTree
        PARTITION BY toYYYYMM(created_at)
        ORDER BY (created_at, station_id, product_code, rec_id)
        """
    )


def _quantize(value: float) -> float:
    return round(value, 3)


def _decision(signal: SignalBundle, policy: dict[str, float | str]) -> dict[str, object]:
    reasons: list[str] = []
    action = "HOLD"
    delta = 0.0
    confidence = _confidence(signal)

    if bool(policy["guardrail_health_offline"]) and signal.health_status.upper() == "OFFLINE":
        return {"action": "REVIEW_REQUIRED", "delta": 0.0, "confidence": 0.95, "reasons": ["HEALTH_OFFLINE"]}
    if bool(policy["guardrail_risk_zone_red"]) and signal.risk_zone.upper() == "RED":
        return {"action": "REVIEW_REQUIRED", "delta": 0.0, "confidence": 0.9, "reasons": ["RISK_RED"]}
    if signal.volume_7d < float(policy["min_volume_7d"]):
        return {"action": "HOLD", "delta": 0.0, "confidence": confidence, "reasons": ["LOW_VOLUME"]}
    if signal.revenue_7d < float(policy["min_revenue_7d"]):
        return {"action": "HOLD", "delta": 0.0, "confidence": confidence, "reasons": ["LOW_VOLUME"]}
    if signal.elasticity_score is None or signal.elasticity_confidence < 0.4:
        return {"action": "HOLD", "delta": 0.0, "confidence": confidence, "reasons": ["LOW_ELASTICITY_CONF"]}

    e = signal.elasticity_score
    margin = signal.margin_pct if signal.margin_pct is not None else 0.0

    if abs(e) < float(policy["elasticity_low_abs"]) and margin < float(policy["target_margin_pct"]):
        action = "INCREASE_PRICE"
        delta = min(float(policy["step_up"]), float(policy["max_delta_per_day"]))
        reasons = ["LOW_ELASTICITY", "LOW_MARGIN"]
    elif e <= -float(policy["elasticity_high_abs"]) and signal.decline_rate >= float(policy["high_decline_rate"]):
        action = "DECREASE_PRICE"
        delta = -min(float(policy["step_down"]), float(policy["max_delta_per_day"]))
        reasons = ["HIGH_ELASTICITY", "HIGH_DECLINE"]
    else:
        reasons = ["MARGIN_STABLE"]

    if action != "HOLD" and confidence < float(policy["min_confidence_to_change"]):
        return {"action": "HOLD", "delta": 0.0, "confidence": confidence, "reasons": ["LOW_CONFIDENCE"]}
    return {"action": action, "delta": delta, "confidence": confidence, "reasons": reasons}




def _confidence(signal: SignalBundle) -> float:
    score = 0.5
    if signal.elasticity_confidence > 0.6:
        score += 0.3
    if signal.volume_7d >= 1000:
        score += 0.2
    if signal.margin_pct is None:
        score -= 0.3
    return max(0.0, min(1.0, score))


def _station_id_u64(station_id: str) -> int:
    try:
        return int(station_id)
    except (TypeError, ValueError):
        return int(hashlib.sha256(station_id.encode("utf-8")).hexdigest()[:16], 16)

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
    rev_rows = (
        db.query(
            Operation.fuel_station_id.label("station_id"),
            func.coalesce(Operation.product_code, "").label("product_code"),
            func.sum(func.coalesce(Operation.amount, 0)).label("revenue_7d"),
        )
        .filter(
            Operation.created_at >= start_7d,
            Operation.fuel_station_id.isnot(None),
            Operation.status.in_([OperationStatus.CAPTURED, OperationStatus.COMPLETED]),
        )
        .group_by(Operation.fuel_station_id, func.coalesce(Operation.product_code, ""))
        .all()
    )
    rev_map = {(str(r.station_id), str(r.product_code or "")): float(r.revenue_7d or 0) for r in rev_rows}

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
                revenue_7d=rev_map.get(key, rev_map.get((station_id, ""), 0.0)),
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

        policy_version = str(policy["version"])
        rec_id = _recommendation_id(signal.station_id, signal.product_code, created_at.date(), policy_version)
        rows.append(
            {
                "rec_id": rec_id,
                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "station_id": _station_id_u64(signal.station_id),
                "product_code": signal.product_code,
                "current_price": _quantize(signal.current_price),
                "recommended_price": new_price,
                "delta_price": _quantize(delta),
                "action": str(decision["action"]).replace("_PRICE", ""),
                "confidence": _quantize(float(decision["confidence"])),
                "reasons": reasons,
                "expected_volume_change_pct": expected_volume_change_pct if expected_volume_change_pct is not None else 0.0,
                "expected_margin_change": expected_margin_change if expected_margin_change is not None else float("nan"),
                "policy_version": policy_version,
                "status": "DRAFT",
                "decided_at": None,
                "decided_by": None,
                "meta": json.dumps({
                    "station_ref": signal.station_id,
                    "health_status": signal.health_status,
                    "risk_zone": signal.risk_zone,
                    "decline_rate": signal.decline_rate,
                    "volume_7d": signal.volume_7d,
                    "revenue_7d": signal.revenue_7d,
                    "window_days": window_days,
                    "margin_unknown": signal.margin_pct is None,
                }, separators=(",", ":")),
            }
        )

    if _ch_enabled() and _ch_ping():
        ensure_price_recommendations_table()
        policy_version = str(policy["version"])
        _ch_exec(
            f"ALTER TABLE neft_geo.fact_price_recommendations DELETE WHERE day = toDate('{created_at.date().isoformat()}') AND policy_version = '{policy_version}'"
        )
        _ch_insert(rows)
    return {"created_at": created_at.isoformat(), "rows": len(rows), "policy_version": policy["version"]}


@dataclass
class ApplyRecommendationResult:
    recommendation_id: str
    status: str
    idempotent: bool


def _snapshot_price_row(row: FuelStationPrice | None) -> dict | None:
    if row is None:
        return None
    return {
        "product_code": row.product_code,
        "price": float(row.price),
        "currency": row.currency,
        "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        "valid_from": row.valid_from.isoformat() if row.valid_from else None,
        "valid_to": row.valid_to.isoformat() if row.valid_to else None,
        "source": row.source.value if hasattr(row.source, "value") else str(row.source),
        "updated_by": row.updated_by,
        "meta": row.meta or {},
    }


def _status_from_action(action_type: str | None) -> str | None:
    mapping = {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "APPLY": "APPLIED"}
    return mapping.get((action_type or "").upper())


def _record_recommendation_action(
    db: Session,
    *,
    rec_id: str,
    action_type: str,
    actor: str | None,
    meta: dict | None = None,
) -> None:
    db.add(
        CommercialRecommendationAction(
            rec_id=rec_id,
            action_type=action_type.upper(),
            actor=actor,
            meta=meta,
        )
    )


def _latest_action_status(db: Session, rec_id: str) -> str | None:
    last_action = (
        db.query(CommercialRecommendationAction)
        .filter(CommercialRecommendationAction.rec_id == rec_id)
        .order_by(CommercialRecommendationAction.ts.desc(), CommercialRecommendationAction.id.desc())
        .first()
    )
    return _status_from_action(last_action.action_type) if last_action else None


def get_recommendation_by_id(db: Session, recommendation_id: str) -> dict | None:
    if not _ch_enabled() or not _ch_ping():
        return None
    escaped_id = _ch_quote(recommendation_id)
    rows = _ch_query(
        f"""
        SELECT rec_id, created_at, station_id, product_code, current_price, recommended_price,
               delta_price, action, confidence, reasons, expected_volume_change_pct, expected_margin_change,
               policy_version, status, decided_at, decided_by, meta
        FROM neft_geo.fact_price_recommendations
        WHERE rec_id = '{escaped_id}'
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    if not rows:
        return None

    row = rows[0]
    meta = json.loads(row.get("meta") or "{}")
    station_ref = str(meta.get("station_ref") or row["station_id"])
    status_override = _latest_action_status(db, recommendation_id)
    return {
        "id": row["rec_id"],
        "created_at": row["created_at"],
        "station_id": station_ref,
        "product_code": row.get("product_code") or "",
        "recommended_price": float(row.get("recommended_price") or 0),
        "action": row.get("action") or "HOLD",
        "policy_version": row.get("policy_version") or "",
        "status": status_override or (row.get("status") or "DRAFT"),
        "meta": meta,
    }


def apply_accepted_recommendation(
    db: Session,
    *,
    recommendation_id: str,
    actor: str | None,
    effective_from: datetime | None,
    comment: str | None,
    request_id: str | None = None,
) -> ApplyRecommendationResult:
    recommendation = get_recommendation_by_id(db, recommendation_id)
    if recommendation is None:
        raise ValueError("recommendation_not_found")

    if recommendation["status"] != "ACCEPTED":
        raise ValueError("recommendation_not_accepted")

    action = str(recommendation.get("action") or "").upper()
    if action not in {"INCREASE", "DECREASE"}:
        raise ValueError("recommendation_action_not_applicable")

    product_code = str(recommendation.get("product_code") or "").strip().upper()
    if not product_code:
        raise ValueError("product_required")

    recommended_price = float(recommendation.get("recommended_price") or 0)
    if recommended_price <= 0:
        raise ValueError("recommended_price_invalid")

    station_id = str(recommendation["station_id"])
    station = db.query(FuelStation).filter(FuelStation.id == station_id).one_or_none()
    if station is None:
        raise ValueError("station_not_found")
    if str(station.status or "").upper() != FuelStationStatus.ACTIVE.value:
        raise ValueError("station_inactive")

    existing = (
        db.query(FuelStationPrice)
        .filter(
            FuelStationPrice.station_id == station_id,
            FuelStationPrice.product_code == product_code,
            FuelStationPrice.meta["applied_rec_id"].astext == recommendation_id,
        )
        .order_by(FuelStationPrice.updated_at.desc())
        .first()
    )
    if existing is not None:
        return ApplyRecommendationResult(recommendation_id=recommendation_id, status="APPLIED", idempotent=True)

    valid_from = effective_from or datetime.now(tz=timezone.utc)
    previous_active = (
        db.query(FuelStationPrice)
        .filter(
            FuelStationPrice.station_id == station_id,
            FuelStationPrice.product_code == product_code,
            FuelStationPrice.status == FuelStationPriceStatus.ACTIVE,
            FuelStationPrice.valid_to.is_(None),
        )
        .order_by(FuelStationPrice.valid_from.desc(), FuelStationPrice.updated_at.desc())
        .first()
    )

    previous_snapshot = _snapshot_price_row(previous_active)
    previous_price = float(previous_active.price) if previous_active is not None else None
    if previous_active is not None:
        previous_active.valid_to = valid_from

    warning_codes: list[str] = []
    if str(station.health_status or "").upper() == "OFFLINE":
        warning_codes.append("HEALTH_OFFLINE")
    if str(station.risk_zone or "").upper() == "RED":
        warning_codes.append("RISK_RED")

    meta = {
        "applied_rec_id": recommendation_id,
        "policy_version": recommendation.get("policy_version"),
        "previous_price": previous_price,
        "comment": comment,
    }
    if warning_codes:
        meta["warnings"] = warning_codes

    new_row = FuelStationPrice(
        station_id=station_id,
        product_code=product_code,
        price=Decimal(str(recommended_price)),
        currency="RUB",
        status=FuelStationPriceStatus.ACTIVE,
        valid_from=valid_from,
        valid_to=None,
        source=FuelStationPriceSource.API,
        updated_by=actor,
        meta=meta,
    )
    db.add(new_row)
    db.flush()

    after_snapshot = _snapshot_price_row(new_row)
    write_price_audit(
        db,
        station_id=station_id,
        product_code=product_code,
        action="APPLY",
        actor=actor,
        source="SYSTEM",
        before=previous_snapshot,
        after=after_snapshot,
        request_id=request_id,
        meta={"rec_id": recommendation_id, "warnings": warning_codes},
    )

    _record_recommendation_action(
        db,
        rec_id=recommendation_id,
        action_type="APPLY",
        actor=actor,
        meta={
            "effective_from": valid_from.isoformat(),
            "comment": comment,
            "station_id": station_id,
            "product_code": product_code,
            "applied_price": recommended_price,
        },
    )
    return ApplyRecommendationResult(recommendation_id=recommendation_id, status="APPLIED", idempotent=False)


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
        SELECT rec_id, created_at, station_id, product_code, current_price, recommended_price,
               delta_price, action, confidence, reasons, expected_volume_change_pct, expected_margin_change,
               policy_version, status, decided_at, decided_by, meta
        FROM neft_geo.fact_price_recommendations
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT {int(limit)}
        """
    )

    station_refs = [str(json.loads(row.get("meta") or "{}").get("station_ref") or row["station_id"]) for row in rows]
    stations = {}
    if station_refs:
        q = db.query(FuelStation).filter(FuelStation.id.in_(station_refs))
        if risk_zone:
            q = q.filter(FuelStation.risk_zone == risk_zone)
        if health_status:
            q = q.filter(FuelStation.health_status == health_status)
        stations = {str(s.id): s for s in q.all()}

    output: list[dict] = []
    for row in rows:
        meta = json.loads(row.get("meta") or "{}")
        station_ref = str(meta.get("station_ref") or row["station_id"])
        station = stations.get(station_ref)
        if (risk_zone or health_status) and not station:
            continue
        effective_status = _latest_action_status(db, row["rec_id"]) or (row.get("status") or "DRAFT")
        output.append(
            {
                "id": row["rec_id"],
                "created_at": row["created_at"],
                "station_id": station_ref,
                "station_name": station.name if station else None,
                "station_address": station.city if station else None,
                "station_lat": station.lat if station else None,
                "station_lon": station.lon if station else None,
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
                "status": effective_status,
                "decided_at": row.get("decided_at"),
                "decided_by": row.get("decided_by"),
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


def _ch_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def update_recommendation_status(
    recommendation_id: str,
    status: str,
    *,
    decided_by: str | None = None,
    comment: str | None = None,
    db: Session | None = None,
) -> bool:
    if not _ch_enabled() or not _ch_ping():
        return False
    ensure_price_recommendations_table()
    decided_at = datetime.now(tz=timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    escaped_by = _ch_quote(decided_by or "system")
    escaped_id = _ch_quote(recommendation_id)
    escaped_comment = _ch_quote(comment or "")
    _ch_exec(
        "ALTER TABLE neft_geo.fact_price_recommendations "
        f"UPDATE status = '{status}', decided_at = toDateTime('{decided_at}'), decided_by = '{escaped_by}', "
        f"meta = if(length(meta)=0, '{{\"comment\":\"{escaped_comment}\"}}', meta) "
        f"WHERE rec_id = '{escaped_id}'"
    )
    if db is not None:
        action_type = {"ACCEPTED": "ACCEPT", "REJECTED": "REJECT"}.get(status.upper())
        if action_type:
            _record_recommendation_action(
                db,
                rec_id=recommendation_id,
                action_type=action_type,
                actor=decided_by,
                meta={"comment": comment},
            )
    return True
