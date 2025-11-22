# services/core-api/app/api/v1/endpoints/operations_read.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud import operations as operations_crud
from app.deps.db import get_db
from app.schemas.operations import OperationList, OperationRead

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=OperationList)
def list_operations(
    db: DbSession,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> OperationList:
    items, total = operations_crud.list_with_total(db, limit=limit, offset=offset)

    return OperationList(
        items=[
            OperationRead(
                operation_id=item.operation_id,
                created_at=item.created_at,
                operation_type=item.operation_type,
                status=item.status,
                merchant_id=item.merchant_id,
                terminal_id=item.terminal_id,
                client_id=item.client_id,
                card_id=item.card_id,
                amount=item.amount,
                currency=item.currency,
                daily_limit=item.daily_limit,
                limit_per_tx=item.limit_per_tx,
                used_today=item.used_today,
                new_used_today=item.new_used_today,
                authorized=item.authorized,
                response_code=item.response_code,
                response_message=item.response_message,
                parent_operation_id=item.parent_operation_id,
                reason=item.reason,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{operation_id}", response_model=OperationRead)
def get_operation(
    operation_id: str,
    db: DbSession,
) -> OperationRead:
    obj = operations_crud.get(db, operation_id=operation_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="operation not found",
        )

    return OperationRead(
        operation_id=obj.operation_id,
        created_at=obj.created_at,
        operation_type=obj.operation_type,
        status=obj.status,
        merchant_id=obj.merchant_id,
        terminal_id=obj.terminal_id,
        client_id=obj.client_id,
        card_id=obj.card_id,
        amount=obj.amount,
        currency=obj.currency,
        daily_limit=obj.daily_limit,
        limit_per_tx=obj.limit_per_tx,
        used_today=obj.used_today,
        new_used_today=obj.new_used_today,
        authorized=obj.authorized,
        response_code=obj.response_code,
        response_message=obj.response_message,
        parent_operation_id=obj.parent_operation_id,
        reason=obj.reason,
    )
