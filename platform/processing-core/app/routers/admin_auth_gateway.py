from fastapi import APIRouter, Depends, Response

from app.services import admin_auth

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.get("/verify", status_code=204)
def verify_admin_token(_: dict = Depends(admin_auth.verify_admin_token)) -> Response:
    return Response(status_code=204)
