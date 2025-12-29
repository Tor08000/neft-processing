from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.documents import Document
from app.models.fuel import FuelTransaction
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerEntry,
    InternalLedgerTransaction,
)
from app.models.invoice import Invoice
from app.models.fleet_intelligence import FITrendEntityType, FITrendMetric, FITrendWindow
from app.models.legal_graph import LegalGraphSnapshot, LegalGraphSnapshotScopeType, LegalNodeType
from app.models.logistics import (
    FuelRouteLink,
    LogisticsDeviationEvent,
    LogisticsNavigatorExplainType,
    LogisticsOrder,
    LogisticsRouteConstraint,
    LogisticsStop,
    LogisticsRiskSignal,
)
from app.models.money_flow import MoneyFlowEvent
from app.models.money_flow_v3 import MoneyFlowLink, MoneyFlowLinkNodeType, MoneyInvariantSnapshot
from app.models.crm import CRMClient, CRMFeatureFlagType, CRMUsageMetric, CRMUsageCounter
from app.models.risk_decision import RiskDecision
from app.services.legal_graph import queries as legal_graph_queries
from app.services.logistics import repository as logistics_repository
from app.services.money_flow.explain import build_money_explain
from app.services.money_flow.errors import MoneyFlowNotFound
from app.services.money_flow.states import MoneyFlowType
from app.services.crm import repository as crm_repository
from app.services.fleet_decision_choice import build_decision_choice as build_decision_choice_service
from app.services.fleet_decision_choice import defaults as decision_choice_defaults
from app.services.fleet_intelligence import actionable as fi_actionable
from app.services.fleet_intelligence import explain as fi_explain
from app.services.fleet_intelligence import repository as fi_repository
from app.services.fleet_intelligence.control import explain as fi_control_explain
from app.services.fuel_intelligence import explain as fuel_intelligence_explain


def get_fuel_tx(db: Session, *, fuel_tx_id: str) -> FuelTransaction | None:
    return db.get(FuelTransaction, fuel_tx_id)


def get_order(db: Session, *, order_id: str) -> LogisticsOrder | None:
    return db.get(LogisticsOrder, order_id)


def get_invoice(db: Session, *, invoice_id: str) -> Invoice | None:
    return db.get(Invoice, invoice_id)


def get_fuel_link(db: Session, *, fuel_tx_id: str) -> FuelRouteLink | None:
    return (
        db.query(FuelRouteLink)
        .filter(FuelRouteLink.fuel_tx_id == fuel_tx_id)
        .order_by(FuelRouteLink.created_at.desc())
        .first()
    )


def get_order_link(db: Session, *, order_id: str) -> FuelRouteLink | None:
    return (
        db.query(FuelRouteLink)
        .filter(FuelRouteLink.order_id == order_id)
        .order_by(FuelRouteLink.created_at.desc())
        .first()
    )


def find_invoice_id_for_fuel(db: Session, *, fuel_tx_id: str) -> str | None:
    link = (
        db.query(MoneyFlowLink)
        .filter(MoneyFlowLink.src_type == MoneyFlowLinkNodeType.FUEL_TX)
        .filter(MoneyFlowLink.src_id == fuel_tx_id)
        .filter(MoneyFlowLink.dst_type == MoneyFlowLinkNodeType.INVOICE)
        .order_by(MoneyFlowLink.created_at.desc())
        .first()
    )
    return link.dst_id if link else None


def find_invoice_id_for_order(db: Session, *, order_id: str) -> str | None:
    link = (
        db.query(MoneyFlowLink)
        .filter(MoneyFlowLink.src_type == MoneyFlowLinkNodeType.LOGISTICS_ORDER)
        .filter(MoneyFlowLink.src_id == order_id)
        .filter(MoneyFlowLink.dst_type == MoneyFlowLinkNodeType.INVOICE)
        .order_by(MoneyFlowLink.created_at.desc())
        .first()
    )
    return link.dst_id if link else None


def build_limits_section(tx: FuelTransaction) -> dict[str, Any] | None:
    meta = tx.meta or {}
    limit_explain = meta.get("limit_explain")
    if isinstance(limit_explain, dict):
        limit_name = limit_explain.get("name") or limit_explain.get("applied_limit_id")
        limit_scope_type = limit_explain.get("scope_type")
        limit_scope_id = limit_explain.get("scope_id")
        limit_explain = {
            **limit_explain,
            "limit_value": limit_explain.get("limit"),
            "limit": {
                "name": limit_name,
                "scope": {
                    "type": limit_scope_type,
                    "id": limit_scope_id,
                }
                if limit_scope_type or limit_scope_id
                else None,
                "period": limit_explain.get("period"),
                "used": limit_explain.get("used"),
                "remaining": limit_explain.get("remaining"),
            },
        }
        return limit_explain
    return None


def build_risk_section(db: Session, *, tx: FuelTransaction) -> dict[str, Any] | None:
    meta = tx.meta or {}
    risk_explain = meta.get("risk_explain")
    if risk_explain is None and not tx.risk_decision_id:
        return None

    payload: dict[str, Any] = {}
    if isinstance(risk_explain, dict):
        payload.update(risk_explain)

    if tx.risk_decision_id:
        decision = db.get(RiskDecision, tx.risk_decision_id)
        if decision:
            payload.setdefault("decision", decision.outcome.value)
            payload.setdefault("score", decision.score)
            payload.setdefault("policy_id", decision.policy_id)
            payload.setdefault("decision_id", decision.decision_id)
            payload.setdefault("factors", decision.reasons)
            payload.setdefault("decision_hash", decision.features_snapshot.get("decision_hash") if isinstance(decision.features_snapshot, dict) else None)
    fraud_signals = meta.get("fraud_signals")
    if isinstance(fraud_signals, list):
        payload["fraud_signals"] = fraud_signals
    return payload


def build_logistics_section(
    db: Session,
    *,
    order_id: str,
    occurred_at: datetime | None,
    client_id: str,
    vehicle_id: str | None,
    driver_id: str | None,
    link: FuelRouteLink | None,
    window_hours: int = 6,
) -> dict[str, Any] | None:
    if not order_id:
        return None

    since = (occurred_at or datetime.utcnow()) - timedelta(hours=window_hours)
    deviation_events = logistics_repository.list_recent_deviation_events(db, order_id=order_id, since=since)
    risk_signals = logistics_repository.list_recent_risk_signals(
        db,
        client_id=client_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        since=since,
    )
    where = _build_where_payload(
        db,
        link=link,
        deviation_events=deviation_events,
        occurred_at=occurred_at,
    )
    threshold = _build_threshold_payload(db, link=link)
    section = {
        "order_id": order_id,
        "route_id": str(link.route_id) if link and link.route_id else None,
        "stop_id": str(link.stop_id) if link and link.stop_id else None,
        "link_type": link.link_type.value if link else None,
        "distance_to_stop_m": link.distance_to_stop_m if link else None,
        "time_delta_minutes": link.time_delta_minutes if link else None,
        "deviation_events": _serialize_deviation_events(deviation_events),
        "risk_signals": _serialize_risk_signals(risk_signals),
        "where": where,
        "threshold": threshold,
    }
    return section


def build_navigator_section(
    db: Session,
    *,
    order_id: str,
    route_id: str | None,
) -> dict[str, Any] | None:
    if not order_id:
        return None

    active_route_id = route_id
    if not active_route_id:
        route = logistics_repository.get_active_route(db, order_id=order_id)
        active_route_id = str(route.id) if route else None
    if not active_route_id:
        return None

    snapshot = logistics_repository.get_latest_route_snapshot(db, route_id=active_route_id)
    if not snapshot:
        return None

    deviation_explains = logistics_repository.list_navigator_explains(
        db,
        route_snapshot_id=str(snapshot.id),
        explain_type=LogisticsNavigatorExplainType.DEVIATION,
    )
    return {
        "route_snapshot_id": str(snapshot.id),
        "provider": snapshot.provider,
        "distance_km": snapshot.distance_km,
        "eta_minutes": snapshot.eta_minutes,
        "created_at": snapshot.created_at.isoformat(),
        "deviation_explains": [
            {
                "id": str(explain.id),
                "payload": explain.payload,
                "created_at": explain.created_at.isoformat(),
            }
            for explain in deviation_explains
        ],
    }


def build_money_section_for_fuel(db: Session, *, fuel_tx_id: str) -> dict[str, Any] | None:
    try:
        explain = build_money_explain(db, MoneyFlowType.FUEL_TX, fuel_tx_id)
    except MoneyFlowNotFound:
        return None

    ledger_entries = None
    if explain.ledger:
        ledger_entries = [
            {
                "account": entry.account,
                "direction": entry.direction,
                "amount": entry.amount,
                "currency": entry.currency,
            }
            for entry in explain.ledger.entries
        ]

    return {
        "flow_state": explain.state.value,
        "ledger": {
            "ledger_transaction_id": explain.ledger.ledger_transaction_id,
            "balanced": explain.ledger.balanced,
            "entries": ledger_entries,
        }
        if explain.ledger
        else None,
        "invariants": explain.invariants,
        "risk": explain.risk,
        "notes": explain.notes,
        "event_id": str(explain.event_id),
        "created_at": explain.created_at.isoformat(),
    }


def build_money_section_for_invoice(db: Session, *, invoice_id: str) -> dict[str, Any] | None:
    invoice = db.get(Invoice, invoice_id)
    ledger_transactions = (
        db.execute(
            select(InternalLedgerTransaction).where(
                InternalLedgerTransaction.external_ref_id == invoice_id
            )
        )
        .scalars()
        .all()
    )
    if not ledger_transactions:
        return None

    entries = (
        db.execute(
            select(InternalLedgerEntry).where(
                InternalLedgerEntry.ledger_transaction_id.in_([tx.id for tx in ledger_transactions])
            )
        )
        .scalars()
        .all()
    )
    account_ids = {entry.account_id for entry in entries}
    accounts = (
        db.execute(select(InternalLedgerAccount).where(InternalLedgerAccount.id.in_(account_ids)))
        .scalars()
        .all()
    )
    account_map = {account.id: account for account in accounts}
    entries_by_tx: dict[str, list[InternalLedgerEntry]] = defaultdict(list)
    for entry in entries:
        entries_by_tx[str(entry.ledger_transaction_id)].append(entry)

    ledger_postings = []
    for tx in ledger_transactions:
        posting_entries = []
        debit_total = 0
        credit_total = 0
        currencies = set()
        for entry in entries_by_tx.get(str(tx.id), []):
            account = account_map.get(entry.account_id)
            account_type = account.account_type.value if account else "UNKNOWN"
            posting_entries.append(
                {
                    "account": account_type,
                    "direction": entry.direction.value,
                    "amount": entry.amount,
                    "currency": entry.currency,
                }
            )
            currencies.add(entry.currency)
            if entry.direction.value == "DEBIT":
                debit_total += entry.amount
            else:
                credit_total += entry.amount
        balanced = debit_total == credit_total and len(currencies) <= 1
        ledger_postings.append(
            {
                "ledger_transaction_id": str(tx.id),
                "transaction_type": tx.transaction_type.value,
                "posted_at": tx.posted_at.isoformat() if tx.posted_at else None,
                "balanced": balanced,
                "entries": posting_entries,
            }
        )

    ledger_postings = sorted(ledger_postings, key=lambda item: item["ledger_transaction_id"])
    money_summary = _build_money_summary(db, invoice=invoice)
    return {"ledger_postings": ledger_postings, "money_summary": money_summary}


def build_money_summary_for_invoice(db: Session, *, invoice_id: str) -> dict[str, Any] | None:
    invoice = db.get(Invoice, invoice_id)
    return _build_money_summary(db, invoice=invoice)


def build_money_summary_for_fuel(db: Session, *, fuel_tx_id: str) -> dict[str, Any] | None:
    invoice_id = find_invoice_id_for_fuel(db, fuel_tx_id=fuel_tx_id)
    if not invoice_id:
        return None
    invoice = db.get(Invoice, invoice_id)
    return _build_money_summary(db, invoice=invoice)


def build_crm_section(db: Session, *, tenant_id: int | None, client_id: str | None) -> dict[str, Any] | None:
    if not client_id:
        return None
    if tenant_id is None:
        client = db.query(CRMClient).filter(CRMClient.id == client_id).one_or_none()
        tenant_id = client.tenant_id if client else None
    if tenant_id is None:
        return None
    subscription = crm_repository.get_active_subscription(db, client_id=client_id)
    tariff = crm_repository.get_tariff(db, tariff_id=subscription.tariff_plan_id) if subscription else None
    contract = crm_repository.get_active_contract(db, client_id=client_id)
    feature_flags = crm_repository.list_feature_flags(db, tenant_id=tenant_id, client_id=client_id)
    flag_map = {flag.feature: bool(flag.enabled) for flag in feature_flags}
    enforcement_flags = {flag.value.lower(): flag_map.get(flag, False) for flag in CRMFeatureFlagType}

    metrics_used: dict[str, int] = {}
    if subscription:
        counters = (
            db.query(CRMUsageCounter)
            .filter(CRMUsageCounter.subscription_id == subscription.id)
            .order_by(CRMUsageCounter.created_at.desc())
            .all()
        )
        metric_map = {
            CRMUsageMetric.CARDS_COUNT: "cards",
            CRMUsageMetric.VEHICLES_COUNT: "vehicles",
            CRMUsageMetric.DRIVERS_COUNT: "drivers",
            CRMUsageMetric.FUEL_TX_COUNT: "fuel_tx",
            CRMUsageMetric.FUEL_VOLUME: "fuel_volume",
            CRMUsageMetric.LOGISTICS_ORDERS: "logistics_orders",
        }
        for counter in counters:
            key = metric_map.get(counter.metric)
            if not key or key in metrics_used:
                continue
            metrics_used[key] = int(counter.value)
            if len(metrics_used) == len(metric_map):
                break

    decision_basis = None
    meta = subscription.meta if subscription else {}
    crm_effect = meta.get("crm_effect") if isinstance(meta, dict) else None
    if isinstance(crm_effect, dict):
        decision_basis = crm_effect.get("reason")
    if not decision_basis:
        decision_basis = "Нет активной подписки" if not subscription else "Разрешено тарифом"

    return {
        "tariff": tariff.id if tariff else None,
        "subscription_status": subscription.status.value if subscription else None,
        "metrics_used": metrics_used,
        "feature_flags": enforcement_flags,
        "decision_flags": [flag.value for flag, enabled in flag_map.items() if enabled],
        "contract": {
            "id": str(contract.id),
            "version": contract.crm_contract_version,
        }
        if contract
        else None,
        "decision_basis": decision_basis,
    }


def build_fleet_intelligence_section(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
    window_days: int = 7,
    fraud_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    scores = fi_repository.latest_scores_for_ids(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        station_id=station_id,
        window_days=window_days,
    )
    driver = scores.get("driver")
    vehicle = scores.get("vehicle")
    station = scores.get("station")
    if not any([driver, vehicle, station]):
        return None
    payload: dict[str, Any] = {}
    if driver:
        payload["driver_behavior"] = {
            "score": driver.score,
            "level": driver.level.value,
            "window_days": driver.window_days,
            "explain": driver.explain,
        }
    if vehicle:
        payload["vehicle_efficiency"] = {
            "efficiency_score": vehicle.efficiency_score,
            "baseline_ml_per_100km": vehicle.baseline_ml_per_100km,
            "actual_ml_per_100km": vehicle.actual_ml_per_100km,
            "delta_pct": vehicle.delta_pct,
            "window_days": vehicle.window_days,
            "explain": vehicle.explain,
        }
    if station:
        payload["station_trust"] = {
            "trust_score": station.trust_score,
            "level": station.level.value,
            "window_days": station.window_days,
            "explain": station.explain,
        }
    fuel_insights = fuel_intelligence_explain.build_fuel_insights(
        db,
        tenant_id=tenant_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        station_id=station_id,
        fraud_signals=fraud_signals,
    )
    if fuel_insights:
        payload["fuel_insights"] = fuel_insights
        payload["fuel_recommendations"] = fuel_insights
    return payload


def build_fuel_insight_section(*, fuel_insights: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not fuel_insights:
        return None
    primary = _select_primary_fuel_insight(fuel_insights)
    details = [
        {
            "code": item.get("code"),
            "title": item.get("title"),
            "what_detected": item.get("what_detected"),
            "why_suspicious": item.get("why_suspicious"),
            "what_to_check": item.get("what_to_check"),
            "severity": item.get("severity"),
        }
        for item in fuel_insights
    ]
    return {
        "primary": primary.get("title") or primary.get("code"),
        "details": details,
        "recommendation": primary.get("recommendation"),
    }


def build_executive_summary(*, sections: dict[str, Any]) -> dict[str, Any] | None:
    if not sections:
        return None
    fleet_control = sections.get("fleet_control") if isinstance(sections.get("fleet_control"), dict) else None
    fleet_insight = sections.get("fleet_insight") if isinstance(sections.get("fleet_insight"), dict) else None
    fleet_intelligence = (
        sections.get("fleet_intelligence") if isinstance(sections.get("fleet_intelligence"), dict) else None
    )
    money_section = sections.get("money") if isinstance(sections.get("money"), dict) else None
    fuel_insights = []
    if isinstance(fleet_intelligence, dict):
        fuel_insights = fleet_intelligence.get("fuel_insights") or []
        if not isinstance(fuel_insights, list):
            fuel_insights = []

    risk_level = _resolve_risk_level(fleet_control, fleet_insight, fuel_insights, money_section)
    open_insights = _count_open_insights(fleet_control, fleet_insight, fuel_insights)
    return {
        "risk_level": risk_level,
        "cost_impact_estimate": _resolve_cost_impact(money_section),
        "open_insights": open_insights,
        "recommended_focus": _resolve_recommended_focus(fleet_control, fleet_insight, fuel_insights, money_section),
    }


def _select_primary_fuel_insight(fuel_insights: list[dict[str, Any]]) -> dict[str, Any]:
    severity_rank = {"WARNING": 2, "INFO": 1}
    return max(fuel_insights, key=lambda item: severity_rank.get(str(item.get("severity")), 0))


def _resolve_risk_level(
    fleet_control: dict[str, Any] | None,
    fleet_insight: dict[str, Any] | None,
    fuel_insights: list[dict[str, Any]],
    money_section: dict[str, Any] | None,
) -> str:
    if fleet_control:
        active = fleet_control.get("active_insight") if isinstance(fleet_control.get("active_insight"), dict) else None
        severity = str(active.get("severity")) if isinstance(active, dict) else None
        if severity in {"CRITICAL", "HIGH"}:
            return "HIGH"
        if severity in {"MEDIUM"}:
            return "MEDIUM"
    if fleet_insight:
        primary = fleet_insight.get("primary_insight") if isinstance(fleet_insight.get("primary_insight"), dict) else None
        level = str(primary.get("level")) if isinstance(primary, dict) else ""
        if level == "VERY_HIGH":
            return "HIGH"
        if level == "HIGH":
            return "MEDIUM"
    if any(item.get("severity") == "WARNING" for item in fuel_insights):
        return "MEDIUM"
    if _money_risk_level(money_section) in {"HIGH", "MEDIUM"}:
        return _money_risk_level(money_section)
    return "LOW"


def _money_risk_level(money_section: dict[str, Any] | None) -> str:
    if not money_section:
        return "LOW"
    risk = money_section.get("risk")
    if isinstance(risk, dict):
        level = str(risk.get("level") or risk.get("severity") or "").upper()
        if level in {"HIGH", "CRITICAL"}:
            return "HIGH"
        if level:
            return "MEDIUM"
    return "LOW"


def _resolve_cost_impact(money_section: dict[str, Any] | None) -> str:
    if not money_section:
        return "Нет данных"
    ledger = money_section.get("ledger") if isinstance(money_section.get("ledger"), dict) else None
    entries = ledger.get("entries") if isinstance(ledger, dict) else None
    if isinstance(entries, list) and entries:
        amounts = [
            (entry.get("amount"), entry.get("currency"))
            for entry in entries
            if entry.get("amount") is not None and entry.get("currency")
        ]
        if amounts:
            amount, currency = max(amounts, key=lambda item: abs(float(item[0])))
            return f"{amount} {currency}"
    return "Нет данных"


def _count_open_insights(
    fleet_control: dict[str, Any] | None,
    fleet_insight: dict[str, Any] | None,
    fuel_insights: list[dict[str, Any]],
) -> int:
    count = len(fuel_insights)
    if fleet_control and fleet_control.get("active_insight"):
        count += 1
    if fleet_insight:
        primary = fleet_insight.get("primary_insight")
        if primary:
            count += 1
        secondary = fleet_insight.get("secondary_insights")
        if isinstance(secondary, list):
            count += len(secondary)
    return count


def _resolve_recommended_focus(
    fleet_control: dict[str, Any] | None,
    fleet_insight: dict[str, Any] | None,
    fuel_insights: list[dict[str, Any]],
    money_section: dict[str, Any] | None,
) -> str:
    codes = [str(item.get("code")) for item in fuel_insights]
    if any("STATION" in code for code in codes):
        return "STATION"
    if any("ROUTE" in code for code in codes):
        return "ROUTE"
    if any("DRIVER" in code for code in codes):
        return "DRIVER"
    if fleet_control:
        active = fleet_control.get("active_insight") if isinstance(fleet_control.get("active_insight"), dict) else None
        entity_type = str(active.get("entity_type")) if isinstance(active, dict) else ""
        if entity_type:
            return entity_type
    if fleet_insight:
        primary = fleet_insight.get("primary_insight") if isinstance(fleet_insight.get("primary_insight"), dict) else None
        insight_type = str(primary.get("type")) if isinstance(primary, dict) else ""
        if insight_type:
            return insight_type
    if money_section and money_section.get("risk"):
        return "FINANCE"
    return "GENERAL"


def build_fleet_control_section(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
) -> dict[str, Any] | None:
    return fi_control_explain.build_fleet_control_section(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        station_id=station_id,
    )


def build_decision_choice_section(
    db: Session,
    *,
    fleet_control: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not fleet_control:
        return None
    active_insight = fleet_control.get("active_insight")
    if not isinstance(active_insight, dict):
        return None
    insight_type = active_insight.get("entity_type")
    if not insight_type:
        return None
    suggested_actions = fleet_control.get("suggested_actions")
    candidate_actions = None
    if isinstance(suggested_actions, list):
        candidate_actions = [
            item.get("action_code")
            for item in suggested_actions
            if isinstance(item, dict) and item.get("action_code")
        ]
    window_days = active_insight.get("window_days") or decision_choice_defaults.DEFAULT_WINDOW_DAYS
    return build_decision_choice_service(
        db,
        insight_type=insight_type,
        candidate_actions=candidate_actions,
        window_days=window_days,
    )


def build_fleet_policy_bundle_section(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
) -> dict[str, Any] | None:
    return fi_control_explain.build_fleet_policy_bundle_section(
        db,
        tenant_id=tenant_id,
        client_id=client_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        station_id=station_id,
    )


def build_fleet_insight_section(
    db: Session,
    *,
    tenant_id: int | None,
    client_id: str | None,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
    window_days: int = 7,
) -> dict[str, Any] | None:
    driver_scores = []
    vehicle_scores = []
    station_scores = []
    if driver_id or vehicle_id or station_id:
        if tenant_id is None or client_id is None:
            return None
        scores = fi_repository.latest_scores_for_ids(
            db,
            tenant_id=tenant_id,
            client_id=client_id,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            station_id=station_id,
            window_days=window_days,
        )
        driver = scores.get("driver")
        vehicle = scores.get("vehicle")
        station = scores.get("station")
        if driver:
            driver_scores.append(driver)
        if vehicle:
            vehicle_scores.append(vehicle)
        if station:
            station_scores.append(station)
    elif client_id:
        driver_scores = fi_repository.list_latest_driver_scores_by_client(
            db,
            client_id=client_id,
            window_days=window_days,
        )
        vehicle_scores = fi_repository.list_latest_vehicle_scores_by_client(
            db,
            client_id=client_id,
            window_days=window_days,
        )
        if tenant_id is not None:
            station_scores = fi_repository.list_latest_station_scores_by_tenant(
                db,
                tenant_id=tenant_id,
                window_days=window_days,
            )

    return fi_actionable.build_fleet_insight_payload(
        driver_scores=driver_scores,
        vehicle_scores=vehicle_scores,
        station_scores=station_scores,
    )


def build_fleet_trends_section(
    db: Session,
    *,
    tenant_id: int,
    driver_id: str | None,
    vehicle_id: str | None,
    station_id: str | None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {}
    if driver_id:
        driver_trend = fi_repository.get_latest_trend_snapshot(
            db,
            tenant_id=tenant_id,
            entity_type=FITrendEntityType.DRIVER,
            entity_id=driver_id,
            metric=FITrendMetric.DRIVER_BEHAVIOR_SCORE,
            window=FITrendWindow.D7,
        )
        if driver_trend:
            payload["driver"] = _serialize_trend(driver_trend, days=7)
    if station_id:
        station_trend = fi_repository.get_latest_trend_snapshot(
            db,
            tenant_id=tenant_id,
            entity_type=FITrendEntityType.STATION,
            entity_id=station_id,
            metric=FITrendMetric.STATION_TRUST_SCORE,
            window=FITrendWindow.D30,
        )
        if station_trend:
            payload["station"] = _serialize_trend(station_trend, days=30)
    if vehicle_id:
        vehicle_trend = fi_repository.get_latest_trend_snapshot(
            db,
            tenant_id=tenant_id,
            entity_type=FITrendEntityType.VEHICLE,
            entity_id=vehicle_id,
            metric=FITrendMetric.VEHICLE_EFFICIENCY_DELTA_PCT,
            window=FITrendWindow.ROLLING,
        )
        if vehicle_trend:
            payload["vehicle"] = _serialize_trend(vehicle_trend, days=30)
    return payload or None


def _serialize_trend(trend, *, days: int) -> dict[str, Any]:
    message = fi_explain.build_trend_message(label=trend.label, days=days)
    return {
        "label": trend.label.value,
        "delta": trend.delta,
        "message": message,
    }


def build_documents_section(db: Session, *, invoice_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    if not invoice_id:
        return None, []
    documents = (
        db.query(Document)
        .filter(Document.source_entity_id == invoice_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    if not documents:
        return None, []

    document_ids = [str(doc.id) for doc in documents]
    snapshot_map = _load_document_snapshot_hashes(db, document_ids)
    payload = {
        "documents": [
            {
                "id": str(doc.id),
                "document_type": doc.document_type.value,
                "status": doc.status.value,
                "number": doc.number,
                "period_from": doc.period_from.isoformat(),
                "period_to": doc.period_to.isoformat(),
                "document_hash": doc.document_hash,
                "snapshot_hash": snapshot_map.get(str(doc.id)),
            }
            for doc in documents
        ]
    }
    return payload, document_ids


def build_graph_section(
    db: Session,
    *,
    tenant_id: int | None,
    node_type: LegalNodeType,
    ref_id: str,
    depth: int,
) -> dict[str, Any] | None:
    if tenant_id is None:
        return None
    trace = legal_graph_queries.trace(
        db,
        tenant_id=tenant_id,
        node_type=node_type,
        ref_id=ref_id,
        depth=depth,
    )
    if not trace.nodes:
        return None
    return {
        "nodes": trace.nodes,
        "edges": trace.edges,
        "layers": trace.layers,
    }


def load_money_flow_event_ids(db: Session, *, flow_type: MoneyFlowType, flow_ref_id: str) -> list[str]:
    events = (
        db.execute(
            select(MoneyFlowEvent)
            .where(MoneyFlowEvent.flow_type == flow_type)
            .where(MoneyFlowEvent.flow_ref_id == flow_ref_id)
            .order_by(MoneyFlowEvent.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [str(event.id) for event in events]


def _serialize_deviation_events(events: Iterable[LogisticsDeviationEvent]) -> list[dict[str, Any]]:
    serialized = [
        {
            "id": str(event.id),
            "event_type": event.event_type.value,
            "ts": event.ts.isoformat(),
            "severity": event.severity.value,
            "stop_id": str(event.stop_id) if event.stop_id else None,
            "distance_from_route_m": event.distance_from_route_m,
            "explain": event.explain,
        }
        for event in events
    ]
    return sorted(serialized, key=lambda item: item["ts"], reverse=True)


def _serialize_risk_signals(events: Iterable[LogisticsRiskSignal]) -> list[dict[str, Any]]:
    serialized = [
        {
            "id": str(event.id),
            "signal_type": event.signal_type.value,
            "severity": event.severity,
            "ts": event.ts.isoformat(),
            "explain": event.explain,
        }
        for event in events
    ]
    return sorted(serialized, key=lambda item: (item["severity"], item["ts"]), reverse=True)


def _build_where_payload(
    db: Session,
    *,
    link: FuelRouteLink | None,
    deviation_events: Iterable[LogisticsDeviationEvent],
    occurred_at: datetime | None,
) -> dict[str, Any]:
    stop_id = link.stop_id if link and link.stop_id else None
    distance_m = link.distance_to_stop_m if link else None
    ts = None
    latest_event = None
    for event in deviation_events:
        if latest_event is None or event.ts > latest_event.ts:
            latest_event = event
    if latest_event:
        ts = latest_event.ts.isoformat()
        if not stop_id and latest_event.stop_id:
            stop_id = latest_event.stop_id
        if distance_m is None and latest_event.distance_from_route_m is not None:
            distance_m = latest_event.distance_from_route_m
    if ts is None and occurred_at:
        ts = occurred_at.isoformat()

    stop_name = None
    stop_payload = None
    if stop_id:
        stop = db.get(LogisticsStop, stop_id)
        stop_name = stop.name if stop else None
        stop_payload = {"id": str(stop_id), "name": stop_name}

    distance_km = None
    if distance_m is not None:
        distance_km = round(distance_m / 1000.0, 3)

    return {
        "stop": stop_payload,
        "distance_km": distance_km,
        "ts": ts,
    }


def _build_threshold_payload(db: Session, *, link: FuelRouteLink | None) -> dict[str, Any]:
    if not link or not link.route_id:
        return {
            "max_deviation_km": None,
            "stop_radius_m": None,
            "allowed_window_min": None,
        }
    constraint = (
        db.query(LogisticsRouteConstraint)
        .filter(LogisticsRouteConstraint.route_id == link.route_id)
        .one_or_none()
    )
    if not constraint:
        return {
            "max_deviation_km": None,
            "stop_radius_m": None,
            "allowed_window_min": None,
        }
    return {
        "max_deviation_km": round(constraint.max_route_deviation_m / 1000.0, 3)
        if constraint.max_route_deviation_m is not None
        else None,
        "stop_radius_m": constraint.max_stop_radius_m,
        "allowed_window_min": constraint.allowed_fuel_window_minutes,
    }


def _build_money_summary(db: Session, *, invoice: Invoice | None) -> dict[str, Any] | None:
    if not invoice:
        return None
    snapshots = (
        db.execute(
            select(MoneyInvariantSnapshot).where(MoneyInvariantSnapshot.flow_ref_id == str(invoice.id))
        )
        .scalars()
        .all()
    )
    invariants = "UNKNOWN"
    if snapshots:
        invariants = "OK" if all(snapshot.passed for snapshot in snapshots) else "FAILED"

    replay_link = None
    if invoice.billing_period_id:
        replay_link = f"/admin/money/replay?client_id={invoice.client_id}&period_id={invoice.billing_period_id}"

    return {
        "charged": invoice.total_with_tax,
        "paid": invoice.amount_paid,
        "due": invoice.amount_due,
        "refunded": invoice.amount_refunded,
        "invariants": invariants,
        "replay_link": replay_link,
    }


def _load_document_snapshot_hashes(db: Session, document_ids: list[str]) -> dict[str, str | None]:
    if not document_ids:
        return {}
    snapshots = (
        db.query(LegalGraphSnapshot)
        .filter(LegalGraphSnapshot.scope_type == LegalGraphSnapshotScopeType.DOCUMENT)
        .filter(LegalGraphSnapshot.scope_ref_id.in_(document_ids))
        .order_by(LegalGraphSnapshot.created_at.desc())
        .all()
    )
    snapshot_map: dict[str, str | None] = {doc_id: None for doc_id in document_ids}
    for snapshot in snapshots:
        if snapshot_map.get(snapshot.scope_ref_id) is None:
            snapshot_map[snapshot.scope_ref_id] = snapshot.snapshot_hash
    return snapshot_map


__all__ = [
    "build_documents_section",
    "build_graph_section",
    "build_limits_section",
    "build_logistics_section",
    "build_money_section_for_fuel",
    "build_money_section_for_invoice",
    "build_money_summary_for_fuel",
    "build_money_summary_for_invoice",
    "build_navigator_section",
    "build_risk_section",
    "build_crm_section",
    "build_fleet_control_section",
    "build_decision_choice_section",
    "build_executive_summary",
    "build_fleet_intelligence_section",
    "build_fleet_insight_section",
    "build_fuel_insight_section",
    "build_fleet_policy_bundle_section",
    "build_fleet_trends_section",
    "find_invoice_id_for_fuel",
    "find_invoice_id_for_order",
    "get_fuel_link",
    "get_fuel_tx",
    "get_invoice",
    "get_order",
    "get_order_link",
    "load_money_flow_event_ids",
]
