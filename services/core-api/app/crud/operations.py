# services/core-api/app/crud/operations.py

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Operation  # каноническая модель журнала операций


class OperationFilters:
    def __init__(
        self,
        *,
        operation_id: Optional[str] = None,
        card_id: Optional[str] = None,
        client_id: Optional[str] = None,
        merchant_id: Optional[str] = None,
        terminal_id: Optional[str] = None,
    ) -> None:
        self.operation_id = operation_id
        self.card_id = card_id
        self.client_id = client_id
        self.merchant_id = merchant_id
        self.terminal_id = terminal_id


def _apply_filters(stmt: Select[tuple[Operation]], filters: OperationFilters) -> Select:
    """Общий хелпер: накладываем where по доступным фильтрам."""
    if filters.operation_id:
        stmt = stmt.where(Operation.operation_id == filters.operation_id)
    if filters.card_id:
        stmt = stmt.where(Operation.card_id == filters.card_id)
    if filters.client_id:
        stmt = stmt.where(Operation.client_id == filters.client_id)
    if filters.merchant_id:
        stmt = stmt.where(Operation.merchant_id == filters.merchant_id)
    if filters.terminal_id:
        stmt = stmt.where(Operation.terminal_id == filters.terminal_id)
    return stmt


def list_operations(
    db: Session,
    *,
    filters: OperationFilters | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Operation]:
    """
    Возвращает список операций с учётом фильтров и пагинации.

    Используется в эндпоинте чтения журнала.
    """
    if filters is None:
        filters = OperationFilters()

    stmt: Select = select(Operation)
    stmt = _apply_filters(stmt, filters)

    stmt = (
        stmt.order_by(Operation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return db.execute(stmt).scalars().all()


def count_operations(
    db: Session,
    *,
    filters: OperationFilters | None = None,
) -> int:
    """
    Возвращает общее количество операций под заданные фильтры.
    Нужно для поля total в ответе API.
    """
    if filters is None:
        filters = OperationFilters()

    stmt: Select = select(func.count())
    stmt = _apply_filters(stmt.select_from(Operation), filters)
    return db.execute(stmt).scalar_one()


def list_with_total(
    db: Session,
    *,
    filters: OperationFilters | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[Sequence[Operation], int]:
    """
    Удобный хелпер, который сразу возвращает (items, total).

    Именно эту функцию ждёт эндпоинт operations_read.
    """
    items = list_operations(db, filters=filters, limit=limit, offset=offset)
    total = count_operations(db, filters=filters)
    return items, total


def get(
    db: Session,
    *,
    operation_id: str,
) -> Optional[Operation]:
    """
    Получить одну операцию по её operation_id.
    """
    stmt: Select = select(Operation).where(Operation.operation_id == operation_id)
    return db.execute(stmt).scalars().first()
