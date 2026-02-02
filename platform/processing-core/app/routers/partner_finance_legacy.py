from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse


router = APIRouter(prefix="/partner", tags=["partner-finance"])


@router.get("/dashboard", include_in_schema=False)
def partner_dashboard_legacy_redirect(request: Request) -> RedirectResponse:
    target_path = "/api/core/partner/finance/dashboard"
    target_url = request.url.replace(path=target_path)
    return RedirectResponse(url=str(target_url), status_code=308)
