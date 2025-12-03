from datetime import date, datetime
import csv
from io import StringIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models.operation import Operation
from app.schemas.reports import (
    BillingDailyReportItem,
    BillingSummaryItem,
    GroupBy,
    TurnoverReportResponse,
)
from app.services.reports import get_turnover_report
from app.services.reports_billing import (
    build_billing_summary_for_date,
    list_billing_summaries,
)

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["reports", "billing"],
)


@router.get("/turnover", response_model=TurnoverReportResponse)
def get_turnover_report_endpoint(
    group_by: GroupBy = Query("client"),
    from_created_at: datetime = Query(..., alias="from"),
    to_created_at: datetime = Query(..., alias="to"),
    client_id: str | None = None,
    card_id: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    db: Session = Depends(get_db),
) -> TurnoverReportResponse:
    """
    Возвращает агрегированный оборот за период по выбранному измерению.
    """
    return get_turnover_report(
        db,
        group_by=group_by,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
        client_id=client_id,
        card_id=card_id,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
    )


@router.get("/billing/daily", response_model=list[BillingDailyReportItem])
def get_daily_billing_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[BillingDailyReportItem]:
    query = (
        db.query(
            func.date(Operation.created_at).label("op_date"),
            Operation.merchant_id,
            func.coalesce(func.sum(Operation.amount), 0).label("total_amount"),
            func.count().label("total_operations"),
        )
        .filter(Operation.operation_type == "CAPTURE")
        .filter(Operation.created_at >= datetime.combine(date_from, datetime.min.time()))
        .filter(Operation.created_at <= datetime.combine(date_to, datetime.max.time()))
    )

    if merchant_id:
        query = query.filter(Operation.merchant_id == merchant_id)

    query = query.group_by("op_date", Operation.merchant_id).order_by("op_date")
    rows = query.all()

    return [
        BillingDailyReportItem(
            date=row.op_date,
            merchant_id=row.merchant_id,
            total_captured_amount=int(row.total_amount or 0),
            total_operations=row.total_operations,
        )
        for row in rows
    ]


@router.post(
    "/billing/summary/rebuild",
    response_model=list[BillingSummaryItem],
    summary="Пересчитать агрегаты биллинга за период",
)
def rebuild_billing_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[BillingSummaryItem]:
    summaries = build_billing_summary_for_date(
        db, date_from=date_from, date_to=date_to, merchant_id=merchant_id
    )

    return [
        BillingSummaryItem(
            id=item.id,
            date=item.date,
            merchant_id=item.merchant_id,
            total_captured_amount=item.total_captured_amount,
            operations_count=item.operations_count,
            status=item.status,
            generated_at=item.generated_at,
            finalized_at=item.finalized_at,
            hash=item.hash,
        )
        for item in summaries
    ]


@router.get(
    "/billing/summary",
    response_model=list[BillingSummaryItem],
    summary="Получить агрегированные суммы CAPTURE",
)
def get_billing_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[BillingSummaryItem]:
    summaries = list_billing_summaries(
        db, date_from=date_from, date_to=date_to, merchant_id=merchant_id
    )

    return [
        BillingSummaryItem(
            id=item.id,
            date=item.date,
            merchant_id=item.merchant_id,
            total_captured_amount=item.total_captured_amount,
            operations_count=item.operations_count,
            status=item.status,
            generated_at=item.generated_at,
            finalized_at=item.finalized_at,
            hash=item.hash,
        )
        for item in summaries
    ]


@router.get("/turnover/export")
def export_turnover_csv_endpoint(
    group_by: GroupBy = Query("client"),
    from_created_at: datetime = Query(..., alias="from"),
    to_created_at: datetime = Query(..., alias="to"),
    client_id: str | None = None,
    card_id: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    db: Session = Depends(get_db),
):
    report = get_turnover_report(
        db,
        group_by=group_by,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
        client_id=client_id,
        card_id=card_id,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
    )

    output = StringIO()
    writer = csv.writer(output, delimiter=";")

    writer.writerow(
        [
            "group_by",
            "client_id",
            "card_id",
            "merchant_id",
            "terminal_id",
            "transaction_count",
            "authorized_amount",
            "captured_amount",
            "refunded_amount",
            "net_turnover",
            "currency",
            "from",
            "to",
        ]
    )

    for item in report.items:
        key = item.group_key
        writer.writerow(
            [
                report.group_by,
                key.client_id or "",
                key.card_id or "",
                key.merchant_id or "",
                key.terminal_id or "",
                item.transaction_count,
                item.authorized_amount,
                item.captured_amount,
                item.refunded_amount,
                item.net_turnover,
                item.currency,
                report.from_created_at.isoformat(),
                report.to_created_at.isoformat(),
            ]
        )

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="turnover_report.csv"'},
    )
