from __future__ import annotations

from app.deps.auth import Actor
from app.models import CRMAuditEvent


def _build_diff(before: dict | None, after: dict | None) -> dict:
    before = before or {}
    after = after or {}
    changed = {}
    for key in set(before) | set(after):
        if before.get(key) != after.get(key):
            changed[key] = {"before": before.get(key), "after": after.get(key)}
    return {"changed": changed}


def audit_create(db, tenant_id: str, entity_type: str, entity_id: str, actor: Actor, payload: dict) -> None:
    db.add(
        CRMAuditEvent(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action="create",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            actor_email=actor.actor_email,
            diff={"changed": payload},
        )
    )


def audit_update(db, tenant_id: str, entity_type: str, entity_id: str, actor: Actor, before: dict, after: dict, action: str = "update") -> None:
    db.add(
        CRMAuditEvent(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            actor_email=actor.actor_email,
            diff=_build_diff(before, after),
        )
    )


def audit_delete(db, tenant_id: str, entity_type: str, entity_id: str, actor: Actor, before: dict) -> None:
    db.add(
        CRMAuditEvent(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action="delete",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            actor_email=actor.actor_email,
            diff={"changed": {"before": before}},
        )
    )


def audit_comment(db, tenant_id: str, entity_type: str, entity_id: str, actor: Actor, payload: dict) -> None:
    db.add(
        CRMAuditEvent(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action="comment_add",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            actor_email=actor.actor_email,
            diff={"changed": payload},
        )
    )
