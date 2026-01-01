from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.explain_diff import ExplainDiffKind, ExplainDiffResponse
from app.schemas.explain_v2 import ExplainActionCatalogItem, ExplainKind, ExplainV2Response
from app.services import admin_auth, client_auth
from app.services.explain_diff_service import build_explain_diff
from app.services.explain_v2_service import (
    build_explain_for_invoice,
    build_explain_for_kpi,
    build_explain_for_marketplace_order,
    build_explain_for_operation,
    list_actions_catalog,
)

router = APIRouter(prefix="/explain", tags=["explain-v2"])

ADMIN_OVERRIDE_ROLES = {"ADMIN", "PLATFORM_ADMIN", "SUPERADMIN"}


def _get_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def _normalize_roles(token: dict) -> set[str]:
    roles = set()
    role = token.get("role")
    if role:
        roles.add(str(role).upper())
    raw_roles = token.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    roles.update({str(item).upper() for item in raw_roles})
    return roles


def _resolve_token_context(request: Request) -> tuple[str, dict]:
    token = _get_bearer_token(request)
    try:
        return "admin", admin_auth.verify_admin_token(token)
    except HTTPException:
        return "client", client_auth.verify_client_token(token)


def _resolve_tenant_id(
    *,
    token: dict,
    token_type: str,
    tenant_override: int | None,
) -> tuple[int, str | None]:
    if token_type == "admin":
        roles = _normalize_roles(token)
        if tenant_override is not None:
            if not roles.intersection(ADMIN_OVERRIDE_ROLES):
                raise HTTPException(status_code=403, detail="forbidden")
            return tenant_override, None
        tenant_id = token.get("tenant_id")
        if tenant_id is None:
            raise HTTPException(status_code=403, detail="Missing tenant context")
        return int(tenant_id), None

    if tenant_override is not None:
        raise HTTPException(status_code=403, detail="forbidden")
    tenant_id = token.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="Missing tenant context")
    return int(tenant_id), str(token.get("client_id") or "") or None


@router.get("", response_model=ExplainV2Response)
def explain_v2(
    request: Request,
    db: Session = Depends(get_db),
    kind: ExplainKind | None = Query(None),
    id: str | None = None,
    kpi_key: str | None = None,
    window_days: int | None = Query(None, ge=1),
    tenant_id: int | None = Query(None, ge=1),
) -> ExplainV2Response:
    token_type, token = _resolve_token_context(request)
    resolved_tenant_id, _client_id = _resolve_tenant_id(
        token=token,
        token_type=token_type,
        tenant_override=tenant_id,
    )

    resolved_kind = kind
    if not resolved_kind and kpi_key:
        resolved_kind = "kpi"
    if not resolved_kind:
        raise HTTPException(status_code=422, detail="kind_required")

    if resolved_kind == "kpi":
        if not kpi_key or window_days is None:
            raise HTTPException(status_code=422, detail="kpi_key_and_window_days_required")
        if window_days not in {7, 30}:
            raise HTTPException(status_code=422, detail="invalid_window_days")
        return build_explain_for_kpi(
            kpi_key=kpi_key,
            window_days=window_days,
            tenant_id=resolved_tenant_id,
        )

    if not id:
        raise HTTPException(status_code=422, detail="id_required")

    try:
        if resolved_kind == "operation":
            return build_explain_for_operation(
                db,
                operation_id=id,
                tenant_id=resolved_tenant_id,
            )
        if resolved_kind == "invoice":
            return build_explain_for_invoice(
                db,
                invoice_id=id,
                tenant_id=resolved_tenant_id,
            )
        if resolved_kind == "marketplace_order":
            return build_explain_for_marketplace_order(
                order_id=id,
                tenant_id=resolved_tenant_id,
            )
    except ValueError as exc:
        if str(exc) in {"operation_not_found", "invoice_not_found"}:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise

    raise HTTPException(status_code=422, detail="unsupported_kind")


@router.get("/actions", response_model=list[ExplainActionCatalogItem])
def explain_actions(
    request: Request,
    kind: ExplainKind | None = Query(None),
    id: str | None = None,
    kpi_key: str | None = None,
    tenant_id: int | None = Query(None, ge=1),
) -> list[ExplainActionCatalogItem]:
    token_type, token = _resolve_token_context(request)
    _resolved_tenant_id, _client_id = _resolve_tenant_id(
        token=token,
        token_type=token_type,
        tenant_override=tenant_id,
    )

    resolved_kind = kind
    if not resolved_kind and kpi_key:
        resolved_kind = "kpi"
    if not resolved_kind:
        raise HTTPException(status_code=422, detail="kind_required")
    if resolved_kind != "kpi" and not id:
        raise HTTPException(status_code=422, detail="id_required")

    return list_actions_catalog(resolved_kind)


@router.get("/diff", response_model=ExplainDiffResponse)
def explain_diff(
    request: Request,
    db: Session = Depends(get_db),
    kind: ExplainDiffKind = Query(...),
    id: str | None = None,
    left_snapshot: str = Query(...),
    right_snapshot: str = Query(...),
    action_id: str | None = None,
    tenant_id: int | None = Query(None, ge=1),
) -> ExplainDiffResponse:
    token_type, token = _resolve_token_context(request)
    resolved_tenant_id, _client_id = _resolve_tenant_id(
        token=token,
        token_type=token_type,
        tenant_override=tenant_id,
    )
    if kind != "kpi" and not id:
        raise HTTPException(status_code=422, detail="id_required")
    roles = _normalize_roles(token)
    is_partner = any("PARTNER" in role for role in roles)
    try:
        return build_explain_diff(
            db,
            kind=kind,
            entity_id=id,
            left_snapshot=left_snapshot,
            right_snapshot=right_snapshot,
            action_id=action_id,
            tenant_id=resolved_tenant_id,
            include_hidden=token_type == "admin",
            include_weights=not is_partner,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "snapshot_not_found":
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc


__all__ = ["router"]
