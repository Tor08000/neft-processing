from __future__ import annotations

from app.providers.base import BaseProvider
from app.schemas import DeviationRequest, DeviationResponse


def compute_deviation(request: DeviationRequest, provider: BaseProvider) -> DeviationResponse:
    return provider.compute_deviation(request)

