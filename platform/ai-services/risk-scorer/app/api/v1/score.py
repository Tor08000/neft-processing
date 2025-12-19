from __future__ import annotations

from fastapi import APIRouter, Depends

from ...model_provider import ScoreModelProvider
from ...schemas import ScoreRequest, ScoreResponse

router = APIRouter(prefix="/v1/score", tags=["score"])


def get_provider() -> ScoreModelProvider:
    return ScoreModelProvider()


@router.post("/", response_model=ScoreResponse)
async def score(payload: ScoreRequest, provider: ScoreModelProvider = Depends(get_provider)) -> ScoreResponse:
    return provider.score(payload)
