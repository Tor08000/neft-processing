from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MoneyFlowDiff:
    mismatched_totals: list[str]
    missing_links: list[str]
    broken_snapshots: list[str]
    recommended_action: str
    missing_links_count: int | None = None
    missing_ledger_postings: int | None = None
    mismatched_invoice_aggregation: list[str] | None = None


def diff_snapshots(expected: dict[str, Any], actual: dict[str, Any]) -> MoneyFlowDiff:
    mismatched: list[str] = []
    expected_invoice = expected.get("invoice", {}) if isinstance(expected.get("invoice"), dict) else {}
    actual_invoice = actual.get("invoice", {}) if isinstance(actual.get("invoice"), dict) else {}

    for key in ("total_with_tax", "amount_paid", "amount_due"):
        if expected_invoice.get(key) != actual_invoice.get(key):
            mismatched.append(key)

    missing_links = []
    if expected.get("links") and not actual.get("links"):
        missing_links.append("links")

    broken_snapshots = []
    if expected.get("snapshots") and not actual.get("snapshots"):
        broken_snapshots.append("snapshots")

    if missing_links:
        recommended_action = "REBUILD_LINKS"
    elif broken_snapshots:
        recommended_action = "RECORD_SNAPSHOTS"
    elif mismatched:
        recommended_action = "REVIEW_TOTALS"
    else:
        recommended_action = "NONE"

    return MoneyFlowDiff(
        mismatched_totals=mismatched,
        missing_links=missing_links,
        broken_snapshots=broken_snapshots,
        recommended_action=recommended_action,
        missing_links_count=None,
        missing_ledger_postings=None,
        mismatched_invoice_aggregation=None,
    )


__all__ = ["MoneyFlowDiff", "diff_snapshots"]
