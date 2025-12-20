from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.settlements import (
    PartnerBalanceResponse,
    PayoutOrderOut,
    SettlementOut,
)
from app.services.settlements import (
    SettlementError,
    approve_settlement,
    confirm_payout,
    generate_settlements_for_date,
    partner_balances,
    send_payout,
)

router = APIRouter(tags=["admin-settlements"])


@router.post("/settlements/generate", response_model=list[SettlementOut])
def generate_settlements(
    date: date = Query(...),
    db: Session = Depends(get_db),
) -> list[SettlementOut]:
    generated = generate_settlements_for_date(db, target_date=date)
    return [SettlementOut.model_validate(item) for item in generated]


@router.post("/settlements/{settlement_id}/approve", response_model=SettlementOut)
def approve(settlement_id: str, db: Session = Depends(get_db)) -> SettlementOut:
    try:
        settlement = approve_settlement(db, settlement_id)
    except SettlementError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SettlementOut.model_validate(settlement)


@router.post("/payouts/{payout_id}/send", response_model=PayoutOrderOut)
def send(payout_id: str, db: Session = Depends(get_db)) -> PayoutOrderOut:
    try:
        payout = send_payout(db, payout_id)
    except SettlementError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return PayoutOrderOut.model_validate(payout)


@router.post("/payouts/{payout_id}/confirm", response_model=PayoutOrderOut)
def confirm(payout_id: str, db: Session = Depends(get_db)) -> PayoutOrderOut:
    try:
        payout = confirm_payout(db, payout_id)
    except SettlementError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return PayoutOrderOut.model_validate(payout)


@router.get("/partners/{partner_id}/balance", response_model=PartnerBalanceResponse)
def partner_balance(partner_id: str, db: Session = Depends(get_db)) -> PartnerBalanceResponse:
    balances = partner_balances(db, partner_id=partner_id)
    return PartnerBalanceResponse(
        partner_id=partner_id,
        balances=[{"currency": item.currency, "balance": item.balance} for item in balances],
    )
