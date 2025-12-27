from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditVisibility
from app.models.legal_graph import LegalEdge, LegalEdgeType, LegalNode, LegalNodeType
from app.services.audit_service import AuditService, RequestContext


@dataclass(frozen=True)
class NodeRef:
    node: LegalNode
    created: bool


@dataclass(frozen=True)
class EdgeRef:
    edge: LegalEdge
    created: bool


class LegalGraphRegistry:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    def get_or_create_node(
        self,
        *,
        tenant_id: int,
        node_type: LegalNodeType,
        ref_id: str,
        ref_table: str | None = None,
        hash_value: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> NodeRef:
        node = (
            self.db.query(LegalNode)
            .filter(LegalNode.tenant_id == tenant_id)
            .filter(LegalNode.node_type == node_type)
            .filter(LegalNode.ref_id == ref_id)
            .one_or_none()
        )
        if node:
            return NodeRef(node=node, created=False)

        node = LegalNode(
            tenant_id=tenant_id,
            node_type=node_type,
            ref_id=ref_id,
            ref_table=ref_table,
            hash=hash_value,
        )
        try:
            with self.db.begin_nested():
                self.db.add(node)
                self.db.flush()
        except IntegrityError:
            node = (
                self.db.query(LegalNode)
                .filter(LegalNode.tenant_id == tenant_id)
                .filter(LegalNode.node_type == node_type)
                .filter(LegalNode.ref_id == ref_id)
                .one()
            )
            return NodeRef(node=node, created=False)

        AuditService(self.db).audit(
            event_type="LEGAL_NODE_CREATED",
            entity_type="legal_node",
            entity_id=str(node.id),
            action="CREATE",
            visibility=AuditVisibility.INTERNAL,
            after={
                "node_type": node_type.value,
                "ref_id": ref_id,
                "ref_table": ref_table,
                "meta": meta,
            },
            request_ctx=self.request_ctx,
        )
        return NodeRef(node=node, created=True)

    def link_edge(
        self,
        *,
        tenant_id: int,
        src_node_id: str,
        dst_node_id: str,
        edge_type: LegalEdgeType,
        meta: dict[str, Any] | None = None,
    ) -> EdgeRef:
        edge = (
            self.db.query(LegalEdge)
            .filter(LegalEdge.tenant_id == tenant_id)
            .filter(LegalEdge.edge_type == edge_type)
            .filter(LegalEdge.src_node_id == src_node_id)
            .filter(LegalEdge.dst_node_id == dst_node_id)
            .one_or_none()
        )
        if edge:
            return EdgeRef(edge=edge, created=False)

        edge = LegalEdge(
            tenant_id=tenant_id,
            edge_type=edge_type,
            src_node_id=src_node_id,
            dst_node_id=dst_node_id,
            meta=meta,
        )
        try:
            with self.db.begin_nested():
                self.db.add(edge)
                self.db.flush()
        except IntegrityError:
            edge = (
                self.db.query(LegalEdge)
                .filter(LegalEdge.tenant_id == tenant_id)
                .filter(LegalEdge.edge_type == edge_type)
                .filter(LegalEdge.src_node_id == src_node_id)
                .filter(LegalEdge.dst_node_id == dst_node_id)
                .one()
            )
            return EdgeRef(edge=edge, created=False)

        AuditService(self.db).audit(
            event_type="LEGAL_EDGE_CREATED",
            entity_type="legal_edge",
            entity_id=str(edge.id),
            action="CREATE",
            visibility=AuditVisibility.INTERNAL,
            after={
                "edge_type": edge_type.value,
                "src_node_id": str(src_node_id),
                "dst_node_id": str(dst_node_id),
                "meta": meta,
            },
            request_ctx=self.request_ctx,
        )
        return EdgeRef(edge=edge, created=True)

    def link(self, **kwargs) -> EdgeRef:
        return self.link_edge(**kwargs)


__all__ = ["EdgeRef", "LegalGraphRegistry", "NodeRef"]
