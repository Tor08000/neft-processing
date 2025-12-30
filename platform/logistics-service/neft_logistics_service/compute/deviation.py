from __future__ import annotations

from neft_logistics_service.providers.base import BaseProvider
from neft_logistics_service.schemas import DeviationRequest, DeviationResponse


def compute_deviation(request: DeviationRequest, provider: BaseProvider) -> DeviationResponse:
    return provider.compute_deviation(request)

