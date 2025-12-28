from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from sqlalchemy.orm import Session

from app.models.unified_explain import UnifiedExplainSnapshot


@dataclass(frozen=True)
class SnapshotPayload:
    snapshot_hash: str
    snapshot_json: dict[str, Any]


def build_snapshot_payload(payload: dict[str, Any]) -> SnapshotPayload:
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    snapshot_hash = sha256(canonical_json.encode("utf-8")).hexdigest()
    return SnapshotPayload(snapshot_hash=snapshot_hash, snapshot_json=json.loads(canonical_json))


def persist_snapshot(
    db: Session,
    *,
    tenant_id: int,
    subject_type: str,
    subject_id: str,
    payload: dict[str, Any],
    actor_type: str | None = None,
    actor_id: str | None = None,
) -> UnifiedExplainSnapshot:
    snapshot_payload = build_snapshot_payload(payload)
    existing = (
        db.query(UnifiedExplainSnapshot)
        .filter(UnifiedExplainSnapshot.tenant_id == tenant_id)
        .filter(UnifiedExplainSnapshot.subject_type == subject_type)
        .filter(UnifiedExplainSnapshot.subject_id == subject_id)
        .filter(UnifiedExplainSnapshot.snapshot_hash == snapshot_payload.snapshot_hash)
        .one_or_none()
    )
    if existing:
        return existing

    snapshot = UnifiedExplainSnapshot(
        tenant_id=tenant_id,
        subject_type=subject_type,
        subject_id=subject_id,
        snapshot_hash=snapshot_payload.snapshot_hash,
        snapshot_json=snapshot_payload.snapshot_json,
        created_by_actor_type=actor_type,
        created_by_actor_id=actor_id,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


__all__ = ["SnapshotPayload", "build_snapshot_payload", "persist_snapshot"]
