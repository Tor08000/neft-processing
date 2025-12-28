from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps.db import get_db
from app.schemas.admin.money_flow import (
    CFOExplainResponse,
    MoneyExplainResponse,
    MoneyHealthResponse,
    MoneyReplayDiffSchema,
    MoneyReplayRequest,
    MoneyReplayResponse,
)
from app.services.money_flow.cfo_explain import build_cfo_explain
from app.services.money_flow.diagnostics import build_money_health
from app.services.money_flow.errors import MoneyFlowNotFound
from app.services.money_flow.explain import build_money_explain
from app.services.money_flow.replay import run_money_flow_replay
from app.services.money_flow.states import MoneyFlowType

router = APIRouter(prefix="/money", tags=["admin-money"])


@router.get("/explain", response_model=MoneyExplainResponse)
def explain_money_flow(
    flow_type: MoneyFlowType = Query(..., description="Money flow type"),
    flow_ref_id: str = Query(..., description="Flow reference id"),
    db: Session = Depends(get_db),
) -> MoneyExplainResponse:
    try:
        explain = build_money_explain(db, flow_type, flow_ref_id)
    except MoneyFlowNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MoneyExplainResponse(
        flow_type=explain.flow_type,
        flow_ref_id=explain.flow_ref_id,
        state=explain.state,
        ledger=explain.ledger,
        invariants=explain.invariants,
        risk=explain.risk,
        notes=explain.notes,
        event_id=explain.event_id,
        created_at=explain.created_at,
    )


@router.get("/health", response_model=MoneyHealthResponse)
def money_health(
    db: Session = Depends(get_db),
    stale_hours: int = Query(24, ge=1, le=168, description="Hours before flow is considered stale"),
) -> MoneyHealthResponse:
    report = build_money_health(db, stale_hours=stale_hours)
    return MoneyHealthResponse(
        orphan_ledger_transactions=report.orphan_ledger_transactions,
        missing_ledger_postings=report.missing_ledger_postings,
        invariant_violations=report.invariant_violations,
        stuck_authorized=report.stuck_authorized,
        stuck_pending_settlement=report.stuck_pending_settlement,
        cross_period_anomalies=report.cross_period_anomalies,
        missing_money_flow_links=report.missing_money_flow_links,
        invoices_missing_subscription_links=report.invoices_missing_subscription_links,
        charges_missing_invoice_links=report.charges_missing_invoice_links,
        charge_key_duplicates=report.charge_key_duplicates,
        segment_gaps_or_overlaps=report.segment_gaps_or_overlaps,
        missing_snapshots=report.missing_snapshots,
        missing_subscription_snapshots=report.missing_subscription_snapshots,
        disconnected_graph=report.disconnected_graph,
        cfo_explain_not_ready=report.cfo_explain_not_ready,
        fuel_missing_ledger_links=report.fuel_missing_ledger_links,
        fuel_missing_billing_period_links=report.fuel_missing_billing_period_links,
        fuel_missing_invoice_links=report.fuel_missing_invoice_links,
        top_offenders=report.top_offenders,
    )


@router.get("/cfo-explain", response_model=CFOExplainResponse)
def cfo_explain(invoice_id: str = Query(..., description="Invoice id"), db: Session = Depends(get_db)) -> CFOExplainResponse:
    try:
        explain = build_cfo_explain(db, invoice_id=invoice_id)
    except MoneyFlowNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CFOExplainResponse(
        invoice_id=explain.invoice_id,
        client_id=explain.client_id,
        currency=explain.currency,
        totals=explain.totals,
        breakdown=explain.breakdown,
        links=explain.links,
        snapshots=explain.snapshots,
        anomalies=explain.anomalies,
        fuel=explain.fuel,
    )


@router.post("/replay", response_model=MoneyReplayResponse)
def replay_money_flow(payload: MoneyReplayRequest, db: Session = Depends(get_db)) -> MoneyReplayResponse:
    result = run_money_flow_replay(
        db,
        client_id=payload.client_id,
        billing_period_id=payload.billing_period_id,
        mode=payload.mode,
        scope=payload.scope,
    )
    diff = None
    if result.diff is not None:
        diff = MoneyReplayDiffSchema(
            mismatched_totals=result.diff.mismatched_totals,
            missing_links=result.diff.missing_links,
            broken_snapshots=result.diff.broken_snapshots,
            recommended_action=result.diff.recommended_action,
            missing_links_count=result.diff.missing_links_count,
            missing_ledger_postings=result.diff.missing_ledger_postings,
            mismatched_invoice_aggregation=result.diff.mismatched_invoice_aggregation,
        )
    return MoneyReplayResponse(
        mode=result.mode,
        scope=result.scope,
        recompute_hash=result.recompute_hash,
        diff=diff,
        links_rebuilt=result.links_rebuilt,
        summary=result.summary,
    )


__all__ = ["router"]
