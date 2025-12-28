from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps.db import get_db
from app.schemas.admin.money_flow import MoneyExplainResponse, MoneyHealthResponse
from app.services.money_flow.diagnostics import build_money_health
from app.services.money_flow.errors import MoneyFlowNotFound
from app.services.money_flow.explain import build_money_explain
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
        top_offenders=report.top_offenders,
    )


__all__ = ["router"]
