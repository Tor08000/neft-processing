from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/admin", tags=["admin-me"])


@router.get("/me", include_in_schema=False)
def get_admin_me_alias(request: Request) -> RedirectResponse:
    target_url = str(request.url.replace(path="/api/core/v1/admin/me"))
    return RedirectResponse(url=target_url, status_code=308)


__all__ = ["router"]
