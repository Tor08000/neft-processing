"""Posting engine to transform business operations into ledger entries."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Callable, Iterable

from app.models.account import AccountType
from app.models.ledger_entry import LedgerDirection, LedgerEntry
from app.repositories.accounts_repository import AccountsRepository
from app.repositories.ledger_repository import LedgerRepository


class PostingOperationType(str, Enum):
    """Supported business operation types for posting."""

    FUEL_PURCHASE = "FUEL_PURCHASE"
    TOPUP = "TOPUP"
    REFUND = "REFUND"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"


@dataclass
class PostingContext:
    """Context required for generating postings."""

    client_id: str
    card_id: str | None
    amount: Decimal
    currency: str
    operation_id: object | None = None


@dataclass
class PostingInstruction:
    """Single movement definition before persistence."""

    account_resolver: Callable[[PostingContext], int]
    direction: LedgerDirection
    amount: Decimal


@dataclass
class PostingResult:
    """Result of posting operation."""

    entries: list[LedgerEntry]
    balances: dict[int, Decimal]
    status: str


TECHNICAL_CLIENT_ID = "NEFT_TECHNICAL"
REVENUE_TARIFF_ID = "REVENUE_CLEARING"
SETTLEMENT_TARIFF_ID = "SETTLEMENT_CLEARING"


class PostingEngine:
    """Convert domain operations into concrete ledger postings."""

    def __init__(self, accounts_repo: AccountsRepository, ledger_repo: LedgerRepository):
        self.accounts_repo = accounts_repo
        self.ledger_repo = ledger_repo
        self._rules: dict[PostingOperationType, Callable[[PostingContext], Iterable[PostingInstruction]]] = {
            PostingOperationType.FUEL_PURCHASE: self._fuel_purchase_instructions,
            PostingOperationType.TOPUP: self._topup_instructions,
            PostingOperationType.REFUND: self._refund_instructions,
        }

    def post(self, operation_type: PostingOperationType, context: PostingContext) -> PostingResult:
        """Persist postings for operation and return created entries and balances."""

        if operation_type not in self._rules:
            raise ValueError(f"Unsupported posting type: {operation_type}")

        instructions = list(self._rules[operation_type](context))
        entries: list[LedgerEntry] = []
        balances: dict[int, Decimal] = {}

        for instruction in instructions:
            account_id = instruction.account_resolver(context)
            entry = self.ledger_repo.post_entry(
                account_id=account_id,
                operation_id=context.operation_id,
                direction=instruction.direction,
                amount=instruction.amount,
                currency=context.currency,
            )
            entries.append(entry)
            balances[account_id] = Decimal(entry.balance_after)

        return PostingResult(entries=entries, balances=balances, status="POSTED")

    def _client_main_account(self, context: PostingContext) -> int:
        account = self.accounts_repo.get_or_create_account(
            client_id=context.client_id,
            card_id=context.card_id,
            currency=context.currency,
            account_type=AccountType.CLIENT_MAIN,
        )
        return account.id

    def _technical_account(self, tariff_id: str, context: PostingContext) -> int:
        account = self.accounts_repo.get_or_create_account(
            client_id=TECHNICAL_CLIENT_ID,
            card_id=None,
            currency=context.currency,
            account_type=AccountType.TECHNICAL,
            tariff_id=tariff_id,
        )
        return account.id

    def _fuel_purchase_instructions(self, context: PostingContext) -> Iterable[PostingInstruction]:
        amount = Decimal(context.amount)
        yield PostingInstruction(
            account_resolver=self._client_main_account,
            direction=LedgerDirection.DEBIT,
            amount=amount,
        )
        yield PostingInstruction(
            account_resolver=lambda ctx: self._technical_account(REVENUE_TARIFF_ID, ctx),
            direction=LedgerDirection.CREDIT,
            amount=amount,
        )

    def _topup_instructions(self, context: PostingContext) -> Iterable[PostingInstruction]:
        amount = Decimal(context.amount)
        yield PostingInstruction(
            account_resolver=lambda ctx: self._technical_account(SETTLEMENT_TARIFF_ID, ctx),
            direction=LedgerDirection.DEBIT,
            amount=amount,
        )
        yield PostingInstruction(
            account_resolver=self._client_main_account,
            direction=LedgerDirection.CREDIT,
            amount=amount,
        )

    def _refund_instructions(self, context: PostingContext) -> Iterable[PostingInstruction]:
        amount = Decimal(context.amount)
        yield PostingInstruction(
            account_resolver=lambda ctx: self._technical_account(REVENUE_TARIFF_ID, ctx),
            direction=LedgerDirection.DEBIT,
            amount=amount,
        )
        yield PostingInstruction(
            account_resolver=self._client_main_account,
            direction=LedgerDirection.CREDIT,
            amount=amount,
        )
