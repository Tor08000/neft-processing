from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.account import AccountOwnerType, AccountType, Account
from app.models.clearing import Clearing
from app.models.ledger_entry import LedgerDirection
from app.models.payout_event import PayoutEvent
from app.models.payout_order import PayoutOrder, PayoutOrderStatus
from app.models.settlement import Settlement, SettlementStatus
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.ledger_repository import LedgerRepository


class SettlementError(Exception):
    """Domain error for settlement lifecycle violations."""


@dataclass
class PartnerBalance:
    currency: str
    balance: Decimal


def generate_settlements_for_date(db: Session, *, target_date: date) -> list[Settlement]:
    """Create draft settlements based on clearing snapshots for the date."""

    clearings = db.query(Clearing).filter(Clearing.batch_date == target_date).all()
    if not clearings:
        return []

    created: list[Settlement] = []
    for clearing in clearings:
        existing = (
            db.query(Settlement)
            .filter(Settlement.merchant_id == clearing.merchant_id)
            .filter(Settlement.currency == clearing.currency)
            .filter(Settlement.period_from == clearing.batch_date)
            .filter(Settlement.period_to == clearing.batch_date)
            .one_or_none()
        )
        if existing:
            created.append(existing)
            continue

        settlement = Settlement(
            merchant_id=clearing.merchant_id,
            partner_id=clearing.merchant_id,
            period_from=clearing.batch_date,
            period_to=clearing.batch_date,
            currency=clearing.currency,
            total_amount=int(clearing.total_amount or 0),
            commission_amount=0,
        )
        db.add(settlement)
        created.append(settlement)

    db.commit()
    for item in created:
        db.refresh(item)
    return created


def approve_settlement(db: Session, settlement_id: str) -> Settlement:
    settlement = db.query(Settlement).filter(Settlement.id == settlement_id).one_or_none()
    if not settlement:
        raise SettlementError("settlement not found")
    if settlement.status != SettlementStatus.DRAFT:
        raise SettlementError("only draft settlements can be approved")

    settlement.status = SettlementStatus.APPROVED
    payout = (
        db.query(PayoutOrder)
        .filter(PayoutOrder.settlement_id == settlement.id)
        .one_or_none()
    )
    if not payout:
        payout = PayoutOrder(
            settlement_id=settlement.id,
            partner_bank_details_ref=None,
            amount=settlement.total_amount - settlement.commission_amount,
            currency=settlement.currency,
            status=PayoutOrderStatus.QUEUED,
        )
        db.add(payout)

    db.commit()
    db.refresh(settlement)
    return settlement


def _post_payout_ledger(db: Session, *, settlement: Settlement, payout: PayoutOrder) -> None:
    accounts_repo = AccountsRepository(db)
    ledger_repo = LedgerRepository(db)

    partner_key = settlement.partner_id or settlement.merchant_id
    currency = payout.currency

    platform_account = accounts_repo.get_or_create_account(
        client_id="PLATFORM",
        owner_type=AccountOwnerType.PLATFORM,
        owner_id="PLATFORM",
        currency=currency,
        account_type=AccountType.TECHNICAL,
        auto_commit=False,
    )
    partner_payable = accounts_repo.get_or_create_account(
        client_id=partner_key,
        owner_type=AccountOwnerType.PARTNER,
        owner_id=partner_key,
        currency=currency,
        account_type=AccountType.TECHNICAL,
        auto_commit=False,
    )

    posting_id = uuid4()
    amount = Decimal(payout.amount)
    now = datetime.now(timezone.utc)

    ledger_repo.post_entry(
        account_id=platform_account.id,
        operation_id=None,
        posting_id=posting_id,
        direction=LedgerDirection.DEBIT,
        amount=amount,
        currency=currency,
        posted_at=now,
        require_operation=False,
        sync_balance=True,
        auto_commit=False,
        entry_id=uuid4(),
    )

    ledger_repo.post_entry(
        account_id=partner_payable.id,
        operation_id=None,
        posting_id=posting_id,
        direction=LedgerDirection.CREDIT,
        amount=amount,
        currency=currency,
        posted_at=now,
        require_operation=False,
        sync_balance=True,
        auto_commit=False,
        entry_id=uuid4(),
    )


def send_payout(db: Session, payout_id: str) -> PayoutOrder:
    payout = db.query(PayoutOrder).filter(PayoutOrder.id == payout_id).one_or_none()
    if not payout:
        raise SettlementError("payout not found")
    settlement = payout.settlement
    if payout.status != PayoutOrderStatus.QUEUED or settlement.status != SettlementStatus.APPROVED:
        raise SettlementError("payout is not ready to be sent")

    payout.status = PayoutOrderStatus.SENT
    payout.error = None
    payout.events.append(PayoutEvent(event_type="SENT"))

    _post_payout_ledger(db, settlement=settlement, payout=payout)

    settlement.status = SettlementStatus.SENT

    db.commit()
    db.refresh(payout)
    return payout


def confirm_payout(db: Session, payout_id: str) -> PayoutOrder:
    payout = db.query(PayoutOrder).filter(PayoutOrder.id == payout_id).one_or_none()
    if not payout:
        raise SettlementError("payout not found")
    settlement = payout.settlement
    if payout.status not in {PayoutOrderStatus.SENT, PayoutOrderStatus.QUEUED}:
        raise SettlementError("payout already finalized")

    payout.status = PayoutOrderStatus.CONFIRMED
    payout.events.append(PayoutEvent(event_type="CONFIRMED"))
    settlement.status = SettlementStatus.CONFIRMED
    db.add(settlement)
    db.commit()
    db.refresh(payout)
    return payout


def partner_balances(db: Session, *, partner_id: str) -> list[PartnerBalance]:
    accounts = (
        db.query(Account)
        .filter(Account.owner_type == AccountOwnerType.PARTNER)
        .filter(Account.owner_id == partner_id)
        .all()
    )
    repo = AccountsRepository(db)
    balances: list[PartnerBalance] = []
    for account in accounts:
        balance = repo.get_balance(account.id)
        balances.append(PartnerBalance(currency=account.currency, balance=Decimal(balance.current_balance or 0)))
    return balances
