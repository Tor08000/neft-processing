from __future__ import annotations

from fastapi import APIRouter, Depends

from app.domains.client.deps import get_client_context
from app.domains.client.repo import ClientRepository
from app.domains.client.schemas import ClientMeResponse
from app.domains.client.service import build_client_me_response

router = APIRouter(prefix="/client/v1", tags=["client-v1"])


@router.get("/health")
def client_v1_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/me", response_model=ClientMeResponse)
def client_v1_me(context: tuple[dict, ClientRepository] = Depends(get_client_context)) -> ClientMeResponse:
    token, repo = context
    return build_client_me_response(token=token, repo=repo)
