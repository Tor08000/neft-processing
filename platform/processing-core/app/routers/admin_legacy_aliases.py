from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.api.dependencies.admin import require_admin_user

router = APIRouter(prefix="/admin", tags=["admin-legacy"], dependencies=[Depends(require_admin_user)])


@router.get("/finance/overview", include_in_schema=False)
def legacy_finance_overview(request: Request) -> RedirectResponse:
    target_url = str(request.url.replace(path="/api/core/v1/admin/finance/overview"))
    return RedirectResponse(url=target_url, status_code=308)


@router.get("/legal/partners", include_in_schema=False)
def legacy_legal_partners(request: Request) -> RedirectResponse:
    target_url = str(request.url.replace(path="/api/core/v1/admin/legal/partners"))
    return RedirectResponse(url=target_url, status_code=308)


@router.get("/audit", include_in_schema=False)
def legacy_audit_feed(request: Request) -> RedirectResponse:
    target_url = str(request.url.replace(path="/api/core/v1/admin/audit"))
    return RedirectResponse(url=target_url, status_code=308)


__all__ = ["router"]
