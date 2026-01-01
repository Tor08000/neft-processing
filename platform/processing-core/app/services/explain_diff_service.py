from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.unified_explain import UnifiedExplainSnapshot
from app.schemas.explain_diff import (
    ExplainDiffActionImpact,
    ExplainDiffDecision,
    ExplainDiffDecisionDiff,
    ExplainDiffEvidenceItem,
    ExplainDiffMeta,
    ExplainDiffReasonItem,
    ExplainDiffResponse,
    ExplainDiffScoreDiff,
    ExplainDiffSnapshotLabel,
)

NOISE_THRESHOLD = 0.03
SPECIAL_SNAPSHOT_KEYS = {"latest", "previous", "baseline"}

ACTION_IMPACT_MAP: dict[str, tuple[float, float]] = {
    "add_limit": (-0.18, 0.72),
    "request_docs": (-0.15, 0.68),
    "manual_review": (-0.07, 0.58),
    "adjust_limits": (-0.12, 0.64),
    "block": (0.2, 0.8),
}


@dataclass(frozen=True)
class _ReasonEntry:
    code: str
    weight: float | None
    hidden: bool


@dataclass(frozen=True)
class _SnapshotData:
    risk_score: float | None
    decision: ExplainDiffDecision | None
    reasons: list[_ReasonEntry]
    evidence_ids: set[str]


def build_explain_diff(
    db: Session,
    *,
    kind: str,
    entity_id: str | None,
    left_snapshot: str,
    right_snapshot: str,
    tenant_id: int,
    include_hidden: bool,
    include_weights: bool,
    action_id: str | None = None,
) -> ExplainDiffResponse:
    left_payload = _load_snapshot_payload(
        db,
        tenant_id=tenant_id,
        kind=kind,
        entity_id=entity_id,
        snapshot_key=left_snapshot,
    )
    right_payload = _load_snapshot_payload(
        db,
        tenant_id=tenant_id,
        kind=kind,
        entity_id=entity_id,
        snapshot_key=right_snapshot,
    )
    left = _parse_snapshot(left_payload)
    right = _parse_snapshot(right_payload)

    reasons_diff = _build_reason_diff(left, right, include_hidden=include_hidden, include_weights=include_weights)
    evidence_diff = _build_evidence_diff(left, right)

    score_before = left.risk_score
    score_after = right.risk_score
    delta = None
    if score_before is not None and score_after is not None:
        delta = round(score_after - score_before, 3)

    action_impact = None
    if action_id:
        action_impact = _build_action_impact(action_id, delta)

    return ExplainDiffResponse(
        meta=ExplainDiffMeta(
            kind=kind,
            entity_id=entity_id,
            left=ExplainDiffSnapshotLabel(snapshot_id=left_snapshot, label="До"),
            right=ExplainDiffSnapshotLabel(snapshot_id=right_snapshot, label="После"),
        ),
        score_diff=ExplainDiffScoreDiff(
            risk_before=score_before,
            risk_after=score_after,
            delta=delta,
        ),
        decision_diff=ExplainDiffDecisionDiff(before=left.decision, after=right.decision),
        reasons_diff=reasons_diff,
        evidence_diff=evidence_diff,
        action_impact=action_impact,
    )


def _load_snapshot_payload(
    db: Session,
    *,
    tenant_id: int,
    kind: str,
    entity_id: str | None,
    snapshot_key: str,
) -> dict[str, Any]:
    query = (
        db.query(UnifiedExplainSnapshot)
        .filter(UnifiedExplainSnapshot.tenant_id == tenant_id)
        .filter(UnifiedExplainSnapshot.subject_type == kind)
    )
    if entity_id:
        query = query.filter(UnifiedExplainSnapshot.subject_id == entity_id)

    normalized = snapshot_key.strip().lower()
    if normalized in SPECIAL_SNAPSHOT_KEYS:
        ordered = query.order_by(UnifiedExplainSnapshot.created_at.desc()).all()
        if not ordered:
            raise ValueError("snapshot_not_found")
        if normalized == "latest":
            snapshot = ordered[0]
        elif normalized == "previous":
            snapshot = ordered[1] if len(ordered) > 1 else None
        else:
            snapshot = ordered[-1]
        if snapshot is None:
            raise ValueError("snapshot_not_found")
        if not isinstance(snapshot.snapshot_json, dict):
            raise ValueError("snapshot_invalid")
        return snapshot.snapshot_json

    generated_at = _parse_generated_at_key(snapshot_key)
    if generated_at is not None:
        snapshot = (
            query.filter(UnifiedExplainSnapshot.created_at <= generated_at)
            .order_by(UnifiedExplainSnapshot.created_at.desc())
            .first()
        )
        if snapshot:
            if not isinstance(snapshot.snapshot_json, dict):
                raise ValueError("snapshot_invalid")
            return snapshot.snapshot_json

    snapshot = query.filter(
        or_(UnifiedExplainSnapshot.id == snapshot_key, UnifiedExplainSnapshot.snapshot_hash == snapshot_key)
    ).one_or_none()
    if not snapshot:
        snapshot = _find_snapshot_by_policy(query, snapshot_key)
    if not snapshot:
        raise ValueError("snapshot_not_found")
    if not isinstance(snapshot.snapshot_json, dict):
        raise ValueError("snapshot_invalid")
    return snapshot.snapshot_json


def _parse_generated_at_key(snapshot_key: str) -> datetime | None:
    if not snapshot_key.startswith("generated_at:"):
        return None
    raw = snapshot_key.split("generated_at:", 1)[1].strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _find_snapshot_by_policy(
    query,
    snapshot_key: str,
) -> UnifiedExplainSnapshot | None:
    snapshots = query.order_by(UnifiedExplainSnapshot.created_at.desc()).all()
    for snapshot in snapshots:
        payload = snapshot.snapshot_json
        if not isinstance(payload, dict):
            continue
        if payload.get("policy_snapshot") == snapshot_key:
            return snapshot
        if payload.get("policy_version") == snapshot_key:
            return snapshot
    return None


def _parse_snapshot(payload: dict[str, Any]) -> _SnapshotData:
    decision = _normalize_decision(payload.get("decision") or payload.get("status"))
    risk_score = _normalize_score(payload.get("risk_score") or payload.get("score"))
    reasons = _extract_reasons(payload)
    evidence_ids = _extract_evidence_ids(payload)
    return _SnapshotData(
        risk_score=risk_score,
        decision=decision,
        reasons=reasons,
        evidence_ids=evidence_ids,
    )


def _normalize_decision(value: Any) -> ExplainDiffDecision | None:
    if not value:
        return None
    normalized = str(value).upper()
    if normalized in {"ALLOW", "APPROVE", "AUTHORIZED"}:
        return "APPROVE"
    if normalized in {"DECLINE", "BLOCK", "DECLINED"}:
        return "DECLINE"
    if normalized in {"REVIEW", "MANUAL_REVIEW"}:
        return "REVIEW"
    if normalized in {"APPROVE", "DECLINE", "REVIEW"}:
        return normalized  # type: ignore[return-value]
    return None


def _normalize_score(score: Any) -> float | None:
    if score is None:
        return None
    try:
        numeric = float(score)
    except (TypeError, ValueError):
        return None
    if numeric > 1:
        numeric = numeric / 100
    return round(min(max(numeric, 0.0), 1.0), 3)


def _extract_reasons(payload: dict[str, Any]) -> list[_ReasonEntry]:
    reasons: list[_ReasonEntry] = []
    raw_reasons = payload.get("reasons")
    if isinstance(raw_reasons, list):
        for item in raw_reasons:
            if not isinstance(item, dict):
                continue
            code = item.get("reason_code") or item.get("code") or item.get("id")
            if not code:
                continue
            weight = item.get("weight") if item.get("weight") is not None else item.get("weight_after")
            hidden = bool(item.get("hidden") or item.get("is_hidden"))
            reasons.append(_ReasonEntry(code=str(code), weight=_coerce_float(weight), hidden=hidden))
        return reasons

    reason_tree = payload.get("reason_tree")
    if isinstance(reason_tree, dict):
        stack = list(reason_tree.get("children") or [])
        while stack:
            node = stack.pop(0)
            if not isinstance(node, dict):
                continue
            code = node.get("id") or node.get("code")
            if code:
                reasons.append(
                    _ReasonEntry(
                        code=str(code),
                        weight=_coerce_float(node.get("weight")),
                        hidden=bool(node.get("hidden") or node.get("is_hidden")),
                    )
                )
            children = node.get("children") or []
            if isinstance(children, list):
                stack.extend(children)
    return reasons


def _extract_evidence_ids(payload: dict[str, Any]) -> set[str]:
    evidence_ids: set[str] = set()
    raw_evidence = payload.get("evidence")
    if isinstance(raw_evidence, list):
        for item in raw_evidence:
            if not isinstance(item, dict):
                continue
            evidence_id = item.get("evidence_id") or item.get("id")
            if evidence_id:
                evidence_ids.add(str(evidence_id))
    return evidence_ids


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_reason_diff(
    left: _SnapshotData,
    right: _SnapshotData,
    *,
    include_hidden: bool,
    include_weights: bool,
) -> list[ExplainDiffReasonItem]:
    left_map = {item.code: item for item in left.reasons if include_hidden or not item.hidden}
    right_map = {item.code: item for item in right.reasons if include_hidden or not item.hidden}
    all_codes = sorted(set(left_map.keys()) | set(right_map.keys()))
    reasons: list[ExplainDiffReasonItem] = []
    for code in all_codes:
        left_entry = left_map.get(code)
        right_entry = right_map.get(code)
        weight_before = left_entry.weight if left_entry else 0.0
        weight_after = right_entry.weight if right_entry else 0.0
        delta = round((weight_after or 0.0) - (weight_before or 0.0), 3)
        if abs(delta) < NOISE_THRESHOLD:
            continue
        if left_entry and not right_entry:
            status = "removed"
        elif right_entry and not left_entry:
            status = "added"
        elif delta > 0:
            status = "strengthened"
        elif delta < 0:
            status = "weakened"
        else:
            status = "unchanged"

        reason = ExplainDiffReasonItem(
            reason_code=code,
            weight_before=weight_before if include_weights else None,
            weight_after=weight_after if include_weights else None,
            delta=delta,
            status=status,
        )
        reasons.append(reason)

    reasons.sort(
        key=lambda item: (
            abs(item.delta),
            abs(item.weight_after or 0.0),
        ),
        reverse=True,
    )
    return reasons


def _build_evidence_diff(left: _SnapshotData, right: _SnapshotData) -> list[ExplainDiffEvidenceItem]:
    removed = sorted(left.evidence_ids - right.evidence_ids)
    added = sorted(right.evidence_ids - left.evidence_ids)
    diff: list[ExplainDiffEvidenceItem] = [
        ExplainDiffEvidenceItem(evidence_id=evidence_id, status="removed") for evidence_id in removed
    ]
    diff.extend(ExplainDiffEvidenceItem(evidence_id=evidence_id, status="added") for evidence_id in added)
    return diff


def _build_action_impact(action_id: str, score_delta: float | None) -> ExplainDiffActionImpact:
    normalized = action_id.strip().lower()
    expected_delta, confidence = ACTION_IMPACT_MAP.get(normalized, (score_delta or 0.0, 0.5))
    return ExplainDiffActionImpact(
        action_id=action_id,
        expected_delta=round(expected_delta, 3),
        confidence=round(confidence, 2),
    )


__all__ = ["build_explain_diff"]
