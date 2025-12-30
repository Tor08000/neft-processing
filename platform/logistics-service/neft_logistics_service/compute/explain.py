from __future__ import annotations

from neft_logistics_service.providers.base import BaseProvider
from neft_logistics_service.schemas import DeviationRequest, EtaRequest, Explain


def explain_eta(request: EtaRequest, provider: BaseProvider) -> Explain:
    return provider.explain_eta(request)


def explain_deviation(request: DeviationRequest, provider: BaseProvider) -> Explain:
    return provider.explain_deviation(request)

