from __future__ import annotations

from app.domains.ledger.enums import EntryType


def build_capture_entry(dimensions: dict) -> dict:
    return {"entry_type": EntryType.CAPTURE, "dimensions": dimensions}


def build_reverse_entry(dimensions: dict) -> dict:
    return {"entry_type": EntryType.REVERSE, "dimensions": dimensions}


def build_payout_entry(dimensions: dict) -> dict:
    return {"entry_type": EntryType.PAYOUT, "dimensions": dimensions}
