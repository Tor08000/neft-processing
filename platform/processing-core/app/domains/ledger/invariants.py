from __future__ import annotations

from decimal import Decimal

from app.domains.ledger.config import REQUIRED_DIMENSIONS
from app.domains.ledger.enums import EntryType, LineDirection
from app.domains.ledger.errors import IdempotencyMismatch, InvariantViolation


class LedgerInvariants:
    @staticmethod
    def assert_balanced(lines: list[dict]) -> None:
        debit = sum(Decimal(str(line["amount"])) for line in lines if line["direction"] == LineDirection.DEBIT.value)
        credit = sum(Decimal(str(line["amount"])) for line in lines if line["direction"] == LineDirection.CREDIT.value)
        if debit != credit:
            raise InvariantViolation("ledger.unbalanced")

    @staticmethod
    def assert_positive(lines: list[dict]) -> None:
        for line in lines:
            amount = Decimal(str(line["amount"]))
            if amount <= 0:
                raise InvariantViolation("ledger.amount_positive")

    @staticmethod
    def assert_single_currency(lines: list[dict]) -> None:
        currencies = {line["currency"] for line in lines}
        if len(currencies) != 1:
            raise InvariantViolation("ledger.single_currency")

    @staticmethod
    def assert_required_dimensions(entry_type: EntryType, dimensions: dict) -> None:
        requirements = REQUIRED_DIMENSIONS.get(entry_type, [])
        for alternatives in requirements:
            if not any(dimensions.get(key) for key in alternatives):
                raise InvariantViolation(f"ledger.required_dimension:{'/'.join(alternatives)}")

    @staticmethod
    def assert_idempotency_match(existing_payload: dict, new_payload: dict) -> None:
        if existing_payload != new_payload:
            raise IdempotencyMismatch("ledger.idempotency_mismatch")
