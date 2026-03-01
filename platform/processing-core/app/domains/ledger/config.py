from __future__ import annotations

from app.domains.ledger.enums import EntryType


REQUIRED_DIMENSIONS: dict[EntryType, list[tuple[str, ...]]] = {
    EntryType.CAPTURE: [("client_id",), ("partner_id",), ("fuel_tx_id", "operation_id")],
    EntryType.REVERSE: [("ref_entry_id", "ref_correlation_id")],
    EntryType.PAYOUT: [("partner_id",), ("payout_id",)],
}

SEED_PLATFORM_ACCOUNTS = {
    "PLATFORM_FEES_REVENUE": "REVENUE",
    "CLEARING": "ASSET",
}
