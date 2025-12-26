from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
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
        object.__setattr__(self, "entity_type", entity_type)
        object.__setattr__(self, "entity_id", entity_id)
        object.__setattr__(self, "invariant_name", invariant_name)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(self, "actual", actual)
        object.__setattr__(self, "ledger_transaction_id", ledger_transaction_id)
        object.__setattr__(self, "violations", list(violations) if violations is not None else None)


__all__ = ["FinancialInvariantViolation"]
