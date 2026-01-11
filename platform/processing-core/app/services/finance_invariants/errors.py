from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class FinancialInvariantViolation(RuntimeError):
    """Raised when financial invariant validation fails."""

    entity_type: str
    entity_id: str
    invariant_name: str
    expected: Any
    actual: Any
    ledger_transaction_id: str | None = None
    violations: list[object] | None = None

    def __init__(
        self,
        *,
        entity_type: str,
        entity_id: str,
        invariant_name: str,
        expected: Any,
        actual: Any,
        ledger_transaction_id: str | None = None,
        violations: Iterable[object] | None = None,
    ) -> None:
        message = f"Financial invariant violated: {invariant_name}"
        super().__init__(message)
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.invariant_name = invariant_name
        self.expected = expected
        self.actual = actual
        self.ledger_transaction_id = ledger_transaction_id
        self.violations = list(violations) if violations is not None else None


__all__ = ["FinancialInvariantViolation"]
