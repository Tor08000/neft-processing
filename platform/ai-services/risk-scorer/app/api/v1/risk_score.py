from __future__ import annotations

from fastapi import APIRouter, Depends

from ...model_provider import RiskScoreModelProvider
from ...schemas import RiskScoreRequest, RiskScoreResponse

router = APIRouter(prefix="/v1/risk-score", tags=["risk-score"])


def get_provider() -> RiskScoreModelProvider:
    return RiskScoreModelProvider()


@router.post("/", response_model=RiskScoreResponse)
async def risk_score(
    payload: RiskScoreRequest,
    provider: RiskScoreModelProvider = Depends(get_provider),
) -> RiskScoreResponse:
    return provider.score(payload)
