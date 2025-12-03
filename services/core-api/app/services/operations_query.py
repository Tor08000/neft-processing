from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.operation import Operation


def list_operations(db: Session, limit: int, offset: int) -> Tuple[List[Operation], int]:
    query = db.query(Operation).order_by(
        Operation.created_at.desc(), Operation.operation_id.desc()
    )
    total = query.count()
    items = query.offset(offset).limit(limit).all()

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
