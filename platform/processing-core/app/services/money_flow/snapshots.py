from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.money_flow_v3 import MoneyInvariantSnapshot, MoneyInvariantSnapshotPhase
from app.services.money_flow.states import MoneyFlowType


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_snapshot_hash(snapshot_json: dict[str, Any]) -> str:
    return sha256(canonical_json(snapshot_json).encode("utf-8")).hexdigest()


def canonicalize_snapshot(snapshot_json: dict[str, Any]) -> dict[str, Any]:
    return json.loads(canonical_json(snapshot_json))


def evaluate_snapshot_invariants(snapshot_json: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    invoice = snapshot_json.get("invoice")
    if isinstance(invoice, dict):
        total_with_tax = int(invoice.get("total_with_tax", 0) or 0)
        amount_paid = int(invoice.get("amount_paid", 0) or 0)
        amount_due = int(invoice.get("amount_due", 0) or 0)
        amount_refunded = int(invoice.get("amount_refunded", 0) or 0)
        if total_with_tax - amount_paid != amount_due:
            violations.append("invoice_balance_mismatch")
        if amount_refunded > amount_paid:
            violations.append("refund_exceeds_paid")

    ledger = snapshot_json.get("ledger")
    if isinstance(ledger, dict) and ledger.get("balanced") is False:
        violations.append("ledger_unbalanced")

    period = snapshot_json.get("period")
    action = snapshot_json.get("action")
    override = snapshot_json.get("override")
    if isinstance(period, dict) and period.get("status") == "LOCKED" and action == "REVERSAL" and not override:
        violations.append("reversal_locked_period")

    return violations


def record_snapshot(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    flow_type: MoneyFlowType,
    flow_ref_id: str,
    event_id: str,
    phase: MoneyInvariantSnapshotPhase,
    snapshot_json: dict[str, Any],
) -> MoneyInvariantSnapshot:
    canonical_snapshot = canonicalize_snapshot(snapshot_json)
    snapshot_hash = build_snapshot_hash(canonical_snapshot)
    violations = evaluate_snapshot_invariants(canonical_snapshot)
    passed = len(violations) == 0

    existing = (
        db.execute(
            select(MoneyInvariantSnapshot)
            .where(MoneyInvariantSnapshot.event_id == event_id)
            .where(MoneyInvariantSnapshot.phase == phase)
            .where(MoneyInvariantSnapshot.snapshot_hash == snapshot_hash)
        )
        .scalars()
        .first()
    )
    if existing:
        return existing

    snapshot = MoneyInvariantSnapshot(
        tenant_id=tenant_id,
        client_id=client_id,
        flow_type=flow_type,
        flow_ref_id=flow_ref_id,
        event_id=event_id,
        phase=phase,
        snapshot_hash=snapshot_hash,
        snapshot_json=canonical_snapshot,
        passed=passed,
        violations=violations or None,
    )
    db.add(snapshot)
    return snapshot


def snapshot_status(snapshots: Iterable[MoneyInvariantSnapshot]) -> dict[str, int | bool]:
    before = 0
    after = 0
    failed = 0
    for snapshot in snapshots:
        if snapshot.phase == MoneyInvariantSnapshotPhase.BEFORE:
            before += 1
        if snapshot.phase == MoneyInvariantSnapshotPhase.AFTER:
            after += 1
        if snapshot.passed is False:
            failed += 1
    return {
        "before_count": before,
        "after_count": after,
        "failed_count": failed,
        "passed": failed == 0 and before > 0 and after > 0,
    }


__all__ = [
    "build_snapshot_hash",
    "canonical_json",
    "canonicalize_snapshot",
    "evaluate_snapshot_invariants",
    "record_snapshot",
    "snapshot_status",
]
