from __future__ import annotations

"""Lightweight metrics collector for the billing pipeline."""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class BillingMetrics:
    """In-memory counters describing billing activity."""

    generated_invoices_total: int = 0
    last_run_generated: int = 0
    billing_errors: int = 0
    billed_amounts: Dict[str, int] = field(default_factory=dict)

    def start_run(self, period_from: str, period_to: str) -> None:
        """Reset per-run counters for a new billing period."""

        self.last_run_generated = 0
        self._current_period_key = f"{period_from}:{period_to}"

    def mark_generated(self, count: int = 1) -> None:
        """Increment counters for successfully created invoices."""

        self.generated_invoices_total += count
        self.last_run_generated += count

    def mark_error(self) -> None:
        """Count billing errors in a best-effort way."""

        self.billing_errors += 1

    def observe_billed_amount(self, amount: int, *, period_key: str | None = None) -> None:
        """Track total billed amount per period."""

        key = period_key or getattr(self, "_current_period_key", "unknown")
        self.billed_amounts[key] = self.billed_amounts.get(key, 0) + amount

    def reset(self) -> None:
        """Reset all collected metrics (primarily for tests)."""

        self.generated_invoices_total = 0
        self.last_run_generated = 0
        self.billing_errors = 0
        self.billed_amounts.clear()


metrics = BillingMetrics()

