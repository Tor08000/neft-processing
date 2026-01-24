from fastapi import APIRouter, Depends, Response

from app.services import partner_auth

router = APIRouter(prefix="/partner/auth", tags=["partner-auth"])


@router.get("/verify", status_code=204)
def verify_partner_token(_: dict = Depends(partner_auth.verify_partner_token)) -> Response:
    return Response(status_code=204)
