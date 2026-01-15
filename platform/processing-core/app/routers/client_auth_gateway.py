from fastapi import APIRouter, Depends, Response

from app.services import client_auth

router = APIRouter(prefix="/client/auth", tags=["client-auth"])


@router.get("/verify", status_code=204)
def verify_client_token(_: dict = Depends(client_auth.verify_client_token)) -> Response:
    return Response(status_code=204)
