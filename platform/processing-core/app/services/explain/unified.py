from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crm import CRMUsageMetric
from app.models.fuel import FuelTransaction
from app.models.invoice import Invoice
from app.models.logistics import (
    FuelRouteLink,
    LogisticsDeviationEvent,
    LogisticsRouteConstraint,
    LogisticsRouteSnapshot,
)
from app.models.money_flow import MoneyFlowEvent
from app.models.money_flow_v3 import MoneyInvariantSnapshot
from app.services.crm import repository as crm_repository
from app.services.explain.recommendations import fuel as fuel_recommendations
from app.services.explain.recommendations import logistics as logistics_recommendations


DECLINE_REASON_MAP = {
    "LIMIT_EXCEEDED_AMOUNT": "Превышение лимита",
    "LIMIT_EXCEEDED_VOLUME": "Превышение лимита",
    "LIMIT_EXCEEDED_COUNT": "Превышение лимита",
    "LIMIT_TIME_WINDOW": "Превышение лимита",
}


def _format_timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _format_period_range(start: str | None, end: str | None) -> str | None:
    parts = list(filter(None, [start, end]))
    return " → ".join(parts) if parts else None


def _distance_km(distance_m: int | None) -> float | None:
    return round(distance_m / 1000, 3) if distance_m is not None else None


def _build_fuel_recommendation_snapshot(fuel_tx: FuelTransaction | None) -> dict[str, Any]:
    meta = fuel_tx.meta if fuel_tx and isinstance(fuel_tx.meta, dict) else {}
    fraud_signals = meta.get("fraud_signals", []) or []
    signals = [signal.get("type") for signal in fraud_signals if isinstance(signal, dict)]
    limit_explain = meta.get("limit_explain") if isinstance(meta.get("limit_explain"), dict) else {}
    limit_period = limit_explain.get("period")
    limit_flags = list(filter(None, [limit_period, fuel_tx.decline_code if fuel_tx else None]))
    common_keys = meta.get("common_recommendations", []) or []
    return {
        "signals": signals,
        "limit_flags": limit_flags,
        "common": common_keys,
    }


def _build_logistics_recommendation_snapshot(event: LogisticsDeviationEvent | None) -> dict[str, Any]:
    explain = event.explain if event and isinstance(event.explain, dict) else {}
    signal = explain.get("signal_type")
    common_keys = explain.get("common_recommendations", []) or []
    return {
        "signals": list(filter(None, [signal])),
        "common": common_keys,
    }


def _build_fuel_fleet_view(db: Session, *, fuel_tx: FuelTransaction | None) -> dict[str, Any] | None:
    if fuel_tx is None:
        return None

    link = (
        db.execute(select(FuelRouteLink).where(FuelRouteLink.fuel_tx_id == fuel_tx.id))
        .scalars()
        .first()
    )
    if link is None:
        return None

    constraint = None
    if link.route_id:
        constraint = (
            db.execute(select(LogisticsRouteConstraint).where(LogisticsRouteConstraint.route_id == link.route_id))
            .scalars()
            .first()
        )

    recommendations = fuel_recommendations.build_recommendations(
        _build_fuel_recommendation_snapshot(fuel_tx)
    )
    return {
        "where": {
            "stop_id": str(link.stop_id) if link.stop_id else None,
            "distance_km": _distance_km(link.distance_to_stop_m),
            "timestamp": _format_timestamp(fuel_tx.occurred_at),
        },
        "threshold": {
            "max_deviation_km": _distance_km(constraint.max_route_deviation_m) if constraint else None,
        },
        "recommendations": recommendations,
    }


def _build_logistics_fleet_view(db: Session, *, route_snapshot_id: str | None) -> dict[str, Any] | None:
    if route_snapshot_id is None:
        return None

    snapshot = db.get(LogisticsRouteSnapshot, route_snapshot_id)
    if snapshot is None:
        return None

    event = (
        db.execute(
            select(LogisticsDeviationEvent)
            .where(LogisticsDeviationEvent.route_id == snapshot.route_id)
            .order_by(LogisticsDeviationEvent.ts.desc())
        )
        .scalars()
        .first()
    )
    if event is None:
        return None

    constraint = (
        db.execute(select(LogisticsRouteConstraint).where(LogisticsRouteConstraint.route_id == snapshot.route_id))
        .scalars()
        .first()
    )
    recommendations = logistics_recommendations.build_recommendations(
        _build_logistics_recommendation_snapshot(event)
    )
    return {
        "where": {
            "stop_id": str(event.stop_id) if event.stop_id else None,
            "distance_km": _distance_km(event.distance_from_route_m),
            "timestamp": _format_timestamp(event.ts),
        },
        "threshold": {
            "max_deviation_km": _distance_km(constraint.max_route_deviation_m) if constraint else None,
        },
        "recommendations": recommendations,
    }


def _build_accountant_view(fuel_tx: FuelTransaction | None) -> dict[str, Any] | None:
    if fuel_tx is None:
        return None
    meta = fuel_tx.meta if isinstance(fuel_tx.meta, dict) else {}
    limit_explain = meta.get("limit_explain") if isinstance(meta.get("limit_explain"), dict) else None
    if limit_explain is None:
        return None

    period_range = _format_period_range(
        limit_explain.get("time_window_start"),
        limit_explain.get("time_window_end"),
    )
    recommendations = fuel_recommendations.build_recommendations(
        _build_fuel_recommendation_snapshot(fuel_tx)
    )
    return {
        "limit": {
            "type": limit_explain.get("period"),
            "value": limit_explain.get("limit"),
            "currency": fuel_tx.currency,
        },
        "period": period_range,
        "reason": DECLINE_REASON_MAP.get(fuel_tx.decline_code, "Превышение лимита"),
        "recommendations": recommendations,
    }


def _build_money_summary(invoice: Invoice | None) -> dict[str, Any]:
    return {
        "charged": int(invoice.total_with_tax or 0) if invoice else 0,
        "paid": int(invoice.amount_paid or 0) if invoice else 0,
        "due": int(invoice.amount_due or 0) if invoice else 0,
        "refunded": int(invoice.amount_refunded or 0) if invoice else 0,
        "currency": invoice.currency if invoice else None,
    }


def _build_money_replay(db: Session, *, flow_ref_id: str | None) -> dict[str, Any]:
    if flow_ref_id is None:
        return {"replay_id": None, "admin_url": None}
    event = (
        db.execute(
            select(MoneyFlowEvent)
            .where(MoneyFlowEvent.flow_ref_id == flow_ref_id)
            .order_by(MoneyFlowEvent.created_at.desc())
        )
        .scalars()
        .first()
    )
    if event is None:
        return {"replay_id": None, "admin_url": None}
    replay_id = str(event.id)
    return {
        "replay_id": replay_id,
        "admin_url": f"/admin/money/replay/{replay_id}",
    }


def _build_invariants(db: Session, *, flow_ref_id: str | None) -> dict[str, Any]:
    if flow_ref_id is None:
        return {"status": "OK", "violations": []}
    snapshots = (
        db.execute(select(MoneyInvariantSnapshot).where(MoneyInvariantSnapshot.flow_ref_id == flow_ref_id))
        .scalars()
        .all()
    )
    violations: list[str] = []
    for snapshot in snapshots:
        if snapshot.violations:
            violations.extend(list(snapshot.violations))
    status = "VIOLATION" if violations else "OK"
    return {
        "status": status,
        "violations": violations,
    }


def _build_crm_section(
    db: Session,
    *,
    client_id: str | None,
    billing_period_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if client_id is None:
        return {
            "tariff": None,
            "subscription": None,
            "metrics_used": {"fuel_tx_count": 0, "drivers": 0},
            "feature_flags": [],
        }, {"allowed": None, "reason": None}

    subscription = crm_repository.get_active_subscription(db, client_id=client_id)
    tariff = crm_repository.get_tariff(db, tariff_id=subscription.tariff_plan_id) if subscription else None

    period_label = None
    if billing_period_id:
        period = crm_repository.get_billing_period(db, billing_period_id=billing_period_id)
        if period:
            period_label = period.start_at.strftime("%Y-%m")

    metrics_used = {"fuel_tx_count": 0, "drivers": 0}
    if subscription and billing_period_id:
        counters = crm_repository.list_usage_counters(
            db,
            subscription_id=str(subscription.id),
            billing_period_id=billing_period_id,
        )
        for counter in counters:
            if counter.metric == CRMUsageMetric.FUEL_TX_COUNT:
                metrics_used["fuel_tx_count"] = int(counter.value)
            if counter.metric == CRMUsageMetric.DRIVERS_COUNT:
                metrics_used["drivers"] = int(counter.value)

    flags = crm_repository.list_feature_flags(db, tenant_id=subscription.tenant_id, client_id=client_id) if subscription else []
    feature_flags = [flag.feature.value for flag in flags if flag.enabled]

    crm_payload = {
        "tariff": {"id": tariff.id, "name": tariff.name} if tariff else None,
        "subscription": {
            "status": subscription.status.value,
            "period": period_label,
        }
        if subscription
        else None,
        "metrics_used": metrics_used,
        "feature_flags": feature_flags,
    }

    crm_effect = {"allowed": None, "reason": None}
    if subscription and isinstance(subscription.meta, dict):
        meta_effect = subscription.meta.get("crm_effect")
        if isinstance(meta_effect, dict):
            crm_effect = meta_effect

    return crm_payload, crm_effect


def build_unified_explain(
    db: Session,
    *,
    fuel_tx_id: str | None = None,
    invoice_id: str | None = None,
    route_snapshot_id: str | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    fuel_tx = db.get(FuelTransaction, fuel_tx_id) if fuel_tx_id else None
    invoice = db.get(Invoice, invoice_id) if invoice_id else None
    resolved_client_id = client_id or (invoice.client_id if invoice else None) or (fuel_tx.client_id if fuel_tx else None)
    billing_period_id = invoice.billing_period_id if invoice else None

    crm_payload, crm_effect = _build_crm_section(
        db,
        client_id=resolved_client_id,
        billing_period_id=str(billing_period_id) if billing_period_id else None,
    )

    return {
        "sources": {
            "fuel": {
                "fleet_view": _build_fuel_fleet_view(db, fuel_tx=fuel_tx),
            },
            "logistics": {
                "fleet_view": _build_logistics_fleet_view(db, route_snapshot_id=route_snapshot_id),
            },
        },
        "accountant_view": _build_accountant_view(fuel_tx),
        "money_summary": _build_money_summary(invoice),
        "money_replay": _build_money_replay(db, flow_ref_id=invoice.id if invoice else None),
        "invariants": _build_invariants(db, flow_ref_id=invoice.id if invoice else None),
        "crm": crm_payload,
        "crm_effect": crm_effect,
    }


__all__ = ["build_unified_explain"]
