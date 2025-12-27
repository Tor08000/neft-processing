from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.audit_log import AuditVisibility
from app.models.legal_graph import (
    LegalGraphSnapshot,
    LegalGraphSnapshotScopeType,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.legal_graph.canonical import hash_snapshot
from app.services.legal_graph.queries import collect_connected_subgraph


@dataclass(frozen=True)
class SnapshotPayload:
    scope_type: LegalGraphSnapshotScopeType
    scope_ref_id: str
    snapshot_hash: str
    snapshot_json: dict
    nodes_count: int
    edges_count: int


class LegalGraphSnapshotService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    def create_snapshot(
        self,
        *,
        tenant_id: int,
        scope_type: LegalGraphSnapshotScopeType,
        scope_ref_id: str,
        depth: int = 3,
        actor_ctx: RequestContext | None = None,
    ) -> LegalGraphSnapshot:
        request_ctx = actor_ctx or self.request_ctx
        payload = self._build_snapshot_payload(
            tenant_id=tenant_id,
            scope_type=scope_type,
            scope_ref_id=scope_ref_id,
            depth=depth,
        )

        existing = (
            self.db.query(LegalGraphSnapshot)
            .filter(LegalGraphSnapshot.tenant_id == tenant_id)
            .filter(LegalGraphSnapshot.scope_type == scope_type)
            .filter(LegalGraphSnapshot.scope_ref_id == scope_ref_id)
            .filter(LegalGraphSnapshot.snapshot_hash == payload.snapshot_hash)
            .one_or_none()
        )
        if existing:
            return existing

        snapshot = LegalGraphSnapshot(
            tenant_id=tenant_id,
            scope_type=scope_type,
            scope_ref_id=scope_ref_id,
            snapshot_hash=payload.snapshot_hash,
            nodes_count=payload.nodes_count,
            edges_count=payload.edges_count,
            snapshot_json=payload.snapshot_json,
            created_by_actor_type=request_ctx.actor_type.value if request_ctx else None,
            created_by_actor_id=request_ctx.actor_id if request_ctx else None,
        )
        self.db.add(snapshot)
        self.db.flush()

        AuditService(self.db).audit(
            event_type="LEGAL_GRAPH_SNAPSHOT_CREATED",
            entity_type="legal_graph_snapshot",
            entity_id=str(snapshot.id),
            action="CREATE",
            visibility=AuditVisibility.INTERNAL,
            after={
                "scope_type": scope_type.value,
                "scope_ref_id": scope_ref_id,
                "snapshot_hash": snapshot.snapshot_hash,
                "nodes_count": snapshot.nodes_count,
                "edges_count": snapshot.edges_count,
            },
            request_ctx=request_ctx,
        )

        return snapshot

    def _build_snapshot_payload(
        self,
        *,
        tenant_id: int,
        scope_type: LegalGraphSnapshotScopeType,
        scope_ref_id: str,
        depth: int,
    ) -> SnapshotPayload:
        nodes, edges = collect_connected_subgraph(
            self.db,
            tenant_id=tenant_id,
            scope_type=scope_type,
            scope_ref_id=scope_ref_id,
            depth=depth,
        )
        if not nodes:
            raise ValueError("snapshot_scope_node_missing")
        snapshot_json = {
            "scope": {"type": scope_type.value, "ref_id": scope_ref_id},
            "nodes": nodes,
            "edges": edges,
        }
        snapshot_hash = hash_snapshot(snapshot_json)
        return SnapshotPayload(
            scope_type=scope_type,
            scope_ref_id=scope_ref_id,
            snapshot_hash=snapshot_hash,
            snapshot_json=snapshot_json,
            nodes_count=len(nodes),
            edges_count=len(edges),
        )


__all__ = ["LegalGraphSnapshotService", "SnapshotPayload"]
