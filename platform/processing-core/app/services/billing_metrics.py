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
    daily_runs: Dict[str, int] = field(default_factory=dict)
    finalize_runs: Dict[str, int] = field(default_factory=dict)
    reconcile_runs: Dict[str, int] = field(default_factory=dict)
    last_run_duration_ms: Dict[str, int] = field(default_factory=dict)

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

    def mark_daily_run(self, status: str, *, duration_ms: int | None = None) -> None:
        """Track billing daily run attempts by status."""

        self.daily_runs[status] = self.daily_runs.get(status, 0) + 1
        if duration_ms is not None:
            self.last_run_duration_ms["billing_daily"] = duration_ms

    def mark_finalize_run(self, status: str, *, duration_ms: int | None = None) -> None:
        """Track finalize-day run attempts by status."""

        self.finalize_runs[status] = self.finalize_runs.get(status, 0) + 1
        if duration_ms is not None:
            self.last_run_duration_ms["billing_finalize"] = duration_ms

    def mark_reconcile_run(self, status: str, *, duration_ms: int | None = None) -> None:
        """Track reconciliation run attempts by status."""

        self.reconcile_runs[status] = self.reconcile_runs.get(status, 0) + 1
        if duration_ms is not None:
            self.last_run_duration_ms["billing_reconcile"] = duration_ms

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
        self.daily_runs.clear()
        self.finalize_runs.clear()
        self.reconcile_runs.clear()
        self.last_run_duration_ms.clear()


metrics = BillingMetrics()
