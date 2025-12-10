from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.operation import Operation

_ORDERING = {
    "created_at_desc": (Operation.created_at.desc(), Operation.operation_id.desc()),
    "created_at_asc": (Operation.created_at.asc(), Operation.operation_id.asc()),
    "amount_desc": (Operation.amount.desc(), Operation.operation_id.desc()),
    "amount_asc": (Operation.amount.asc(), Operation.operation_id.asc()),
    "risk_score_desc": (Operation.risk_score.desc(), Operation.operation_id.desc()),
    "risk_score_asc": (Operation.risk_score.asc(), Operation.operation_id.asc()),
}


def list_operations(
    db: Session,
    limit: int,
    offset: int,
    *,
    operation_type: Optional[str] = None,
    status: Optional[str] = None,
    merchant_id: Optional[str] = None,
    terminal_id: Optional[str] = None,
    client_id: Optional[str] = None,
    card_id: Optional[str] = None,
    from_created_at=None,
    to_created_at=None,
    min_amount: Optional[int] = None,
    max_amount: Optional[int] = None,
    mcc: Optional[str] = None,
    product_category: Optional[str] = None,
    tx_type: Optional[str] = None,
    response_code: Optional[str] = None,
    risk_results: Optional[Sequence[str]] = None,
    risk_min_score: Optional[float] = None,
    risk_max_score: Optional[float] = None,
    order_by: str = "created_at_desc",
) -> Tuple[List[Operation], int]:
    order_clause = _ORDERING.get(order_by) or _ORDERING["created_at_desc"]
    query = db.query(Operation)

    if operation_type:
        query = query.filter(Operation.operation_type == operation_type)
    if status:
        query = query.filter(Operation.status == status)
    if merchant_id:
        query = query.filter(Operation.merchant_id == merchant_id)
    if terminal_id:
        query = query.filter(Operation.terminal_id == terminal_id)
    if client_id:
        query = query.filter(Operation.client_id == client_id)
    if card_id:
        query = query.filter(Operation.card_id == card_id)
    if from_created_at:
        query = query.filter(Operation.created_at >= from_created_at)
    if to_created_at:
        query = query.filter(Operation.created_at <= to_created_at)
    if min_amount is not None:
        query = query.filter(Operation.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Operation.amount <= max_amount)
    if mcc:
        query = query.filter(Operation.mcc == mcc)
    if product_category:
        query = query.filter(Operation.product_category == product_category)
    if tx_type:
        query = query.filter(Operation.tx_type == tx_type)
    if response_code:
        query = query.filter(Operation.response_code == response_code)
    if risk_results:
        query = query.filter(Operation.risk_result.in_(risk_results))
    if risk_min_score is not None:
        query = query.filter(Operation.risk_score >= risk_min_score)
    if risk_max_score is not None:
        query = query.filter(Operation.risk_score <= risk_max_score)

    total = query.count()
    items = query.order_by(*order_clause).offset(offset).limit(limit).all()

    return items, total


def get_operation_timeline(db: Session, operation_id: str) -> List[Operation]:
    root = (
        db.query(Operation).filter(Operation.operation_id == operation_id).first()
    )
    if not root:
        return []

    return (
        db.query(Operation)
        .filter(
            or_(
                Operation.operation_id == operation_id,
                Operation.parent_operation_id == operation_id,
            )
        )
        .order_by(Operation.created_at.asc(), Operation.operation_id.asc())
        .all()
    )
