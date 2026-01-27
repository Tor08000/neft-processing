from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.api.dependencies.admin import require_admin_user

router = APIRouter(
    prefix="/admin/runtime",
    tags=["admin-runtime"],
    dependencies=[Depends(require_admin_user)],
)


@router.get("/summary", include_in_schema=False)
def legacy_runtime_summary(request: Request) -> RedirectResponse:
    target_url = str(request.url.replace(path="/api/core/v1/admin/runtime/summary"))
    return RedirectResponse(url=target_url, status_code=308)


__all__ = ["router"]
