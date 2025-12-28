from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, Literal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.legal_graph import LegalEdge, LegalGraphSnapshotScopeType, LegalNode, LegalNodeType


Direction = Literal["upstream", "downstream", "both"]


@dataclass(frozen=True)
class TraceResult:
    nodes: list[dict]
    edges: list[dict]
    layers: list[list[dict]]


def get_node(
    db: Session,
    *,
    tenant_id: int,
    node_type: LegalNodeType,
    ref_id: str,
) -> LegalNode | None:
    return (
        db.query(LegalNode)
        .filter(LegalNode.tenant_id == tenant_id)
        .filter(LegalNode.node_type == node_type)
        .filter(LegalNode.ref_id == ref_id)
        .one_or_none()
    )


def trace(
    db: Session,
    *,
    tenant_id: int,
    node_type: LegalNodeType,
    ref_id: str,
    depth: int = 3,
    direction: Direction = "both",
) -> TraceResult:
    start_node = get_node(db, tenant_id=tenant_id, node_type=node_type, ref_id=ref_id)
    if not start_node:
        return TraceResult(nodes=[], edges=[], layers=[])

    current_ids = {start_node.id}
    seen_ids = {start_node.id}
    edges: dict[str, LegalEdge] = {}
    layers: list[list[str]] = [[start_node.id]]

    for _ in range(max(depth, 0)):
        if not current_ids:
            break
        edge_rows = _edges_for_nodes(db, tenant_id=tenant_id, node_ids=current_ids)
        next_ids: set[str] = set()
        for edge in edge_rows:
            edges[str(edge.id)] = edge
            if direction in {"downstream", "both"} and edge.src_node_id in current_ids and edge.dst_node_id not in seen_ids:
                next_ids.add(edge.dst_node_id)
            if direction in {"upstream", "both"} and edge.dst_node_id in current_ids and edge.src_node_id not in seen_ids:
                next_ids.add(edge.src_node_id)
        seen_ids.update(next_ids)
        current_ids = next_ids
        if current_ids:
            layers.append(list(current_ids))

    nodes = _nodes_by_ids(db, tenant_id=tenant_id, node_ids=seen_ids)
    serialized_nodes = _serialize_nodes(nodes)
    node_by_id = {
        node.id: {"node_type": node.node_type.value, "ref_id": node.ref_id}
        for node in nodes
    }
    layers_serialized = [
        sorted(
            [node_by_id[node_id] for node_id in layer_ids if node_id in node_by_id],
            key=lambda item: (item["node_type"], item["ref_id"]),
        )
        for layer_ids in layers
    ]
    return TraceResult(
        nodes=serialized_nodes,
        edges=_serialize_edges(nodes, edges.values()),
        layers=layers_serialized,
    )


def collect_connected_subgraph(
    db: Session,
    *,
    tenant_id: int,
    scope_type: LegalGraphSnapshotScopeType,
    scope_ref_id: str,
    depth: int | None = None,
) -> tuple[list[dict], list[dict]]:
    scope_node = get_node(
        db,
        tenant_id=tenant_id,
        node_type=LegalNodeType(scope_type.value),
        ref_id=scope_ref_id,
    )
    if not scope_node:
        return [], []

    pending_ids = {scope_node.id}
    seen_ids = {scope_node.id}
    edges: dict[str, LegalEdge] = {}
    remaining = depth if depth is not None else None

    while pending_ids:
        edge_rows = _edges_for_nodes(db, tenant_id=tenant_id, node_ids=pending_ids)
        pending_ids = set()
        for edge in edge_rows:
            edges[str(edge.id)] = edge
            for node_id in (edge.src_node_id, edge.dst_node_id):
                if node_id not in seen_ids:
                    seen_ids.add(node_id)
                    pending_ids.add(node_id)
        if remaining is not None:
            remaining -= 1
            if remaining <= 0:
                break

    nodes = _nodes_by_ids(db, tenant_id=tenant_id, node_ids=seen_ids)
    return _serialize_nodes(nodes), _serialize_edges(nodes, edges.values())


def _edges_for_nodes(
    db: Session,
    *,
    tenant_id: int,
    node_ids: Iterable[str],
) -> list[LegalEdge]:
    node_ids = list(node_ids)
    if not node_ids:
        return []
    return (
        db.query(LegalEdge)
        .filter(LegalEdge.tenant_id == tenant_id)
        .filter(or_(LegalEdge.src_node_id.in_(node_ids), LegalEdge.dst_node_id.in_(node_ids)))
        .all()
    )


def _nodes_by_ids(db: Session, *, tenant_id: int, node_ids: Iterable[str]) -> list[LegalNode]:
    node_ids = list(node_ids)
    if not node_ids:
        return []
    return (
        db.query(LegalNode)
        .filter(LegalNode.tenant_id == tenant_id)
        .filter(LegalNode.id.in_(node_ids))
        .all()
    )


def _serialize_nodes(nodes: Sequence[LegalNode]) -> list[dict]:
    return sorted(
        [
            {
                "node_type": node.node_type.value,
                "ref_id": node.ref_id,
                "ref_table": node.ref_table,
                "hash": node.hash,
            }
            for node in nodes
        ],
        key=lambda item: (item["node_type"], item["ref_id"]),
    )


def _serialize_edges(nodes: Sequence[LegalNode], edges: Iterable[LegalEdge]) -> list[dict]:
    node_map = {node.id: node for node in nodes}
    serialized = []
    for edge in edges:
        src_node = node_map.get(edge.src_node_id)
        dst_node = node_map.get(edge.dst_node_id)
        if not src_node or not dst_node:
            continue
        serialized.append(
            {
                "edge_type": edge.edge_type.value,
                "src": {"node_type": src_node.node_type.value, "ref_id": src_node.ref_id},
                "dst": {"node_type": dst_node.node_type.value, "ref_id": dst_node.ref_id},
                "meta": edge.meta,
            }
        )
    return sorted(
        serialized,
        key=lambda item: (item["edge_type"], item["src"]["node_type"], item["src"]["ref_id"], item["dst"]["node_type"], item["dst"]["ref_id"]),
    )


__all__ = ["TraceResult", "collect_connected_subgraph", "get_node", "trace"]
