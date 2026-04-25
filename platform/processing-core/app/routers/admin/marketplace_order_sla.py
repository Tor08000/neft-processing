from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.marketplace_order_sla import OrderSlaConsequence, OrderSlaEvaluation
from app.schemas.marketplace.sla import (
    OrderSlaConsequenceOut,
    OrderSlaConsequencesResponse,
    OrderSlaEvaluationOut,
    OrderSlaEvaluationsResponse,
)
from app.security.rbac.guard import require_permission


router = APIRouter(prefix="/marketplace/orders", tags=["admin-marketplace-sla"])


@router.get("/{order_id}/sla", response_model=OrderSlaEvaluationsResponse)
def list_order_sla_evaluations(
    order_id: str,
    db: Session = Depends(get_db),
    _principal=Depends(require_permission("admin:contracts:*")),
) -> OrderSlaEvaluationsResponse:
    evaluations = (
        db.query(OrderSlaEvaluation)
        .filter(OrderSlaEvaluation.order_id == order_id)
        .order_by(OrderSlaEvaluation.created_at.desc())
        .all()
    )
    if not evaluations:
        raise HTTPException(status_code=404, detail="order_sla_not_found")
    return OrderSlaEvaluationsResponse(
        items=[
            OrderSlaEvaluationOut(
                id=str(item.id),
                order_id=item.order_id,
                contract_id=str(item.contract_id),
                obligation_id=str(item.obligation_id),
                period_start=item.period_start,
                period_end=item.period_end,
                measured_value=item.measured_value,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                breach_reason=item.breach_reason,
                breach_severity=item.breach_severity.value if item.breach_severity else None,
                created_at=item.created_at,
            )
            for item in evaluations
        ]
    )


@router.get("/{order_id}/consequences", response_model=OrderSlaConsequencesResponse)
def list_order_sla_consequences(
    order_id: str,
    db: Session = Depends(get_db),
    _principal=Depends(require_permission("admin:contracts:*")),
) -> OrderSlaConsequencesResponse:
    consequences = (
        db.query(OrderSlaConsequence)
        .filter(OrderSlaConsequence.order_id == order_id)
        .order_by(OrderSlaConsequence.created_at.desc())
        .all()
    )
    return OrderSlaConsequencesResponse(
        items=[
            OrderSlaConsequenceOut(
                id=str(item.id),
                order_id=item.order_id,
                evaluation_id=str(item.evaluation_id),
                consequence_type=item.consequence_type.value
                if hasattr(item.consequence_type, "value")
                else str(item.consequence_type),
                amount=item.amount,
                currency=item.currency,
                billing_invoice_id=str(item.billing_invoice_id) if item.billing_invoice_id else None,
                billing_refund_id=str(item.billing_refund_id) if item.billing_refund_id else None,
                ledger_tx_id=str(item.ledger_tx_id) if item.ledger_tx_id else None,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                created_at=item.created_at,
            )
            for item in consequences
        ]
    )
