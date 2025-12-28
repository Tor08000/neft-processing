from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any

from sqlalchemy.orm import Session

from app.services.money_flow.diff import MoneyFlowDiff, diff_snapshots


class MoneyReplayMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    COMPARE = "COMPARE"
    REBUILD_LINKS = "REBUILD_LINKS"


class MoneyReplayScope(str, Enum):
    SUBSCRIPTIONS = "SUBSCRIPTIONS"
    FUEL = "FUEL"
    ALL = "ALL"


@dataclass(frozen=True)
class MoneyReplayResult:
    mode: MoneyReplayMode
    scope: MoneyReplayScope
    recompute_hash: str | None
    diff: MoneyFlowDiff | None
    links_rebuilt: int | None


def build_recompute_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def run_money_flow_replay(
    db: Session,
    *,
    client_id: str,
    billing_period_id: str,
    mode: MoneyReplayMode,
    scope: MoneyReplayScope,
    expected_snapshot: dict[str, Any] | None = None,
    actual_snapshot: dict[str, Any] | None = None,
) -> MoneyReplayResult:
    del db
    recompute_hash = None
    diff = None
    links_rebuilt = None

    if mode == MoneyReplayMode.DRY_RUN:
        recompute_hash = build_recompute_hash(
            {
                "client_id": client_id,
                "billing_period_id": billing_period_id,
                "scope": scope.value,
            }
        )
    elif mode == MoneyReplayMode.COMPARE:
        diff = diff_snapshots(expected_snapshot or {}, actual_snapshot or {})
    elif mode == MoneyReplayMode.REBUILD_LINKS:
        links_rebuilt = 0

    return MoneyReplayResult(
        mode=mode,
        scope=scope,
        recompute_hash=recompute_hash,
        diff=diff,
        links_rebuilt=links_rebuilt,
    )


__all__ = [
    "MoneyReplayMode",
    "MoneyReplayScope",
    "MoneyReplayResult",
    "build_recompute_hash",
    "run_money_flow_replay",
]
