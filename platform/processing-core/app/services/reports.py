from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Hashable, Iterable, List

from sqlalchemy.orm import Session

from app.schemas.reports import (
    GroupBy,
    TurnoverGroupKey,
    TurnoverItem,
    TurnoverReportResponse,
    TurnoverTotals,
)
from app.schemas.transactions import TransactionSchema
from app.services.transactions import list_transactions


@dataclass
class _TurnoverAccumulator:
    group_key: TurnoverGroupKey
    transaction_count: int = 0
    authorized_amount: int = 0
    captured_amount: int = 0
    refunded_amount: int = 0
    net_turnover: int = 0
    currency: str = "RUB"


def _build_group_key(group_by: GroupBy, tx: TransactionSchema) -> tuple[Hashable, TurnoverGroupKey]:
    if group_by == "client":
        key: tuple[Hashable, ...] = ("client", tx.client_id)
        group_key = TurnoverGroupKey(client_id=tx.client_id)
    elif group_by == "card":
        key = ("card", tx.card_id)
        group_key = TurnoverGroupKey(card_id=tx.card_id)
    elif group_by == "merchant":
        key = ("merchant", tx.merchant_id)
        group_key = TurnoverGroupKey(merchant_id=tx.merchant_id)
    elif group_by == "terminal":
        key = ("terminal", tx.terminal_id)
        group_key = TurnoverGroupKey(terminal_id=tx.terminal_id)
    elif group_by == "station":
        key = ("station", tx.merchant_id, tx.terminal_id)
        group_key = TurnoverGroupKey(
            merchant_id=tx.merchant_id, terminal_id=tx.terminal_id
        )
    else:
        raise ValueError(f"Unsupported group_by value: {group_by}")

    return key, group_key


EXCLUDED_STATUSES = {"CANCELLED", "ERROR"}


def aggregate_transactions_for_turnover(
    transactions: Iterable[TransactionSchema],
    *,
    group_by: GroupBy,
    from_created_at: datetime,
    to_created_at: datetime,
) -> TurnoverReportResponse:
    groups: Dict[Hashable, _TurnoverAccumulator] = {}

    for tx in transactions:
        if tx.status in EXCLUDED_STATUSES:
            continue

        net_turnover = tx.captured_amount - tx.refunded_amount
        key, group_key = _build_group_key(group_by, tx)

        if key not in groups:
            groups[key] = _TurnoverAccumulator(group_key=group_key, currency=tx.currency)

        agg = groups[key]
        agg.transaction_count += 1
        agg.authorized_amount += tx.authorized_amount
        agg.captured_amount += tx.captured_amount
        agg.refunded_amount += tx.refunded_amount
        agg.net_turnover += net_turnover

    items: List[TurnoverItem] = [
        TurnoverItem(
            group_key=agg.group_key,
            transaction_count=agg.transaction_count,
            authorized_amount=agg.authorized_amount,
            captured_amount=agg.captured_amount,
            refunded_amount=agg.refunded_amount,
            net_turnover=agg.net_turnover,
            currency=agg.currency,
        )
        for agg in groups.values()
    ]

    totals = TurnoverTotals(
        transaction_count=sum(item.transaction_count for item in items),
        authorized_amount=sum(item.authorized_amount for item in items),
        captured_amount=sum(item.captured_amount for item in items),
        refunded_amount=sum(item.refunded_amount for item in items),
        net_turnover=sum(item.net_turnover for item in items),
        currency="RUB" if not items else items[0].currency,
    )

    return TurnoverReportResponse(
        items=items,
        totals=totals,
        group_by=group_by,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
    )


def get_turnover_report(
    db: Session,
    *,
    group_by: GroupBy,
    from_created_at: datetime,
    to_created_at: datetime,
    client_id: str | None = None,
    card_id: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
) -> TurnoverReportResponse:
    transactions_page = list_transactions(
        db,
        limit=0,
        offset=0,
        client_id=client_id,
        card_id=card_id,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
        no_pagination=True,
    )

    return aggregate_transactions_for_turnover(
        transactions_page.items,
        group_by=group_by,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
    )
