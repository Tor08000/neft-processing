from datetime import datetime
import csv
from io import StringIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.reports import GroupBy, TurnoverReportResponse
from app.services.reports import get_turnover_report

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
