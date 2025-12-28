from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ResourceContext:
    resource_type: Literal[
        "BILLING_PERIOD",
        "INVOICE",
        "PAYOUT_BATCH",
        "ACCOUNTING_EXPORT",
        "DOCUMENT",
        "CLOSING_PACKAGE",
    ]
    tenant_id: int
    client_id: str | None
    status: str | None


__all__ = ["ResourceContext"]
