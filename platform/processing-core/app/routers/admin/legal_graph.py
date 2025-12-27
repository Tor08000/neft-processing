from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.legal_graph import LegalGraphSnapshotScopeType, LegalNodeType, LegalGraphSnapshot
from app.services.legal_graph.completeness import check_billing_period_completeness
from app.services.legal_graph.queries import get_node, trace
from app.services.policy import actor_from_token

router = APIRouter(prefix="/legal-graph", tags=["legal-graph"])


def _require_compliance_access(token: dict) -> None:
    actor = actor_from_token(token)
    roles = {role.upper() for role in (actor.roles or [])}
    if roles.intersection({"ADMIN", "COMPLIANCE"}):
        return
    raise HTTPException(status_code=403, detail="forbidden")


def _tenant_id_from_token(token: dict) -> int:
    return int(token.get("tenant_id") or 0)


@router.get("/nodes/{node_type}/{ref_id}")
def admin_get_legal_node(
    node_type: str,
    ref_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    _require_compliance_access(token)
    tenant_id = _tenant_id_from_token(token)
    try:
        parsed_type = LegalNodeType(node_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_node_type") from exc

    node = get_node(db, tenant_id=tenant_id, node_type=parsed_type, ref_id=ref_id)
    if not node:
        raise HTTPException(status_code=404, detail="legal_node_not_found")

    trace_result = trace(db, tenant_id=tenant_id, node_type=parsed_type, ref_id=ref_id, depth=1)
    return {
        "node": {
            "node_type": node.node_type.value,
            "ref_id": node.ref_id,
            "ref_table": node.ref_table,
            "hash": node.hash,
            "created_at": node.created_at,
        },
        "nodes": trace_result.nodes,
        "edges": trace_result.edges,
        "layers": trace_result.layers,
    }


@router.get("/trace/{node_type}/{ref_id}")
def admin_trace_legal_graph(
    node_type: str,
    ref_id: str,
    depth: int = Query(3, ge=1, le=10),
    direction: str = Query("both", pattern="^(both|upstream|downstream)$"),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    _require_compliance_access(token)
    tenant_id = _tenant_id_from_token(token)
    try:
        parsed_type = LegalNodeType(node_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_node_type") from exc

    trace_result = trace(
        db,
        tenant_id=tenant_id,
        node_type=parsed_type,
        ref_id=ref_id,
        depth=depth,
        direction=direction,  # type: ignore[arg-type]
    )
    if not trace_result.nodes:
        raise HTTPException(status_code=404, detail="legal_node_not_found")
    return {"nodes": trace_result.nodes, "edges": trace_result.edges, "layers": trace_result.layers}


@router.get("/snapshot/{scope_type}/{ref_id}")
def admin_get_legal_snapshot(
    scope_type: str,
    ref_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    _require_compliance_access(token)
    tenant_id = _tenant_id_from_token(token)
    try:
        parsed_scope = LegalGraphSnapshotScopeType(scope_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_scope_type") from exc

    snapshot = (
        db.query(LegalGraphSnapshot)
        .filter(LegalGraphSnapshot.tenant_id == tenant_id)
        .filter(LegalGraphSnapshot.scope_type == parsed_scope)
        .filter(LegalGraphSnapshot.scope_ref_id == ref_id)
        .order_by(LegalGraphSnapshot.created_at.desc())
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="snapshot_not_found")

    return {
        "id": str(snapshot.id),
        "scope_type": snapshot.scope_type.value,
        "scope_ref_id": snapshot.scope_ref_id,
        "snapshot_hash": snapshot.snapshot_hash,
        "nodes_count": snapshot.nodes_count,
        "edges_count": snapshot.edges_count,
        "snapshot_json": snapshot.snapshot_json,
        "created_at": snapshot.created_at,
        "created_by_actor_type": snapshot.created_by_actor_type,
        "created_by_actor_id": snapshot.created_by_actor_id,
    }


@router.get("/completeness/billing-period/{period_id}")
def admin_check_billing_period_completeness(
    period_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin_user),
) -> dict:
    _require_compliance_access(token)
    tenant_id = _tenant_id_from_token(token)
    result = check_billing_period_completeness(db, tenant_id=tenant_id, period_id=period_id)
    return {
        "ok": result.ok,
        "missing_nodes": result.missing_nodes,
        "missing_edges": result.missing_edges,
        "blocking_reasons": result.blocking_reasons,
    }


__all__ = ["router"]
