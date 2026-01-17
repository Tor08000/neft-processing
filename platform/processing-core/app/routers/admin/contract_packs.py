from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.schemas.admin.contract_packs import (
    ContractPackGenerateRequest,
    ContractPackGenerateResponse,
    ContractPackInfo,
)
from app.services.audit_service import AuditService, request_context_from_request
from app.services.contract_pack_service import ContractPackService


router = APIRouter(prefix="/contracts", tags=["admin-contracts"])

ALLOWED_ROLES = {"NEFT_SUPERADMIN", "NEFT_FINANCE", "NEFT_SALES"}


def _extract_roles(token: dict) -> set[str]:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    role = token.get("role")
    if role:
        roles.append(role)
    return {str(item).upper() for item in roles}


def _ensure_role(token: dict) -> None:
    if not _extract_roles(token).intersection(ALLOWED_ROLES):
        raise HTTPException(status_code=403, detail="forbidden_admin_role")


@router.post("/generate", response_model=ContractPackGenerateResponse)
def generate_contract_pack(
    payload: ContractPackGenerateRequest,
    request: Request,
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> ContractPackGenerateResponse:
    _ensure_role(token)
    service = ContractPackService(db)
    try:
        result = service.generate(
            org_id=payload.org_id,
            format=payload.format,
            language=payload.language,
            as_of=payload.as_of,
            include_pricing=payload.include_pricing,
            include_legal_terms=payload.include_legal_terms,
        )
    except ValueError as exc:
        if str(exc) == "org_not_found":
            raise HTTPException(status_code=404, detail="org_not_found") from exc
        raise

    request_ctx = request_context_from_request(request, token=token)
    AuditService(db).audit(
        event_type="CONTRACT_PACK_GENERATED",
        entity_type="contract_pack",
        entity_id=result.contract_pack_id,
        action="CONTRACT_PACK_GENERATED",
        after={
            "org_id": payload.org_id,
            "snapshot_hash": result.entitlements_snapshot_hash,
            "pack_hash": result.pack_hash,
            "format": payload.format,
            "object_key": result.object_key,
        },
        request_ctx=request_ctx,
    )

    return ContractPackGenerateResponse(
        contract_pack_id=result.contract_pack_id,
        status="GENERATED",
        download_url=result.download_url,
        hash=result.pack_hash,
        entitlements_snapshot_hash=result.entitlements_snapshot_hash,
    )


@router.get("/packs", response_model=list[ContractPackInfo])
def list_contract_packs(
    org_id: int = Query(...),
    token: dict = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> list[ContractPackInfo]:
    _ensure_role(token)
    service = ContractPackService(db)
    return [ContractPackInfo(**item) for item in service.list_packs(org_id=org_id)]
