from __future__ import annotations

from neft_logistics_service.providers.base import BaseProvider
from neft_logistics_service.schemas import EtaRequest, EtaResponse


def compute_eta(request: EtaRequest, provider: BaseProvider) -> EtaResponse:
    return provider.compute_eta(request)

