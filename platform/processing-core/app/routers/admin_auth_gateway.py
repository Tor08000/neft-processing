from fastapi import APIRouter, Depends, Response

from app.services import admin_auth

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])
v1_router = APIRouter(prefix="/v1/admin/auth", tags=["admin-auth"])


@router.get("/verify", status_code=204)
def verify_admin_token(_: dict = Depends(admin_auth.verify_admin_token)) -> Response:
    return Response(status_code=204)


@v1_router.get("/verify", status_code=204)
def verify_admin_token_v1(_: dict = Depends(admin_auth.verify_admin_token)) -> Response:
    return Response(status_code=204)
