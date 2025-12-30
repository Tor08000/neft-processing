from __future__ import annotations

from app.providers.base import BaseProvider
from app.schemas import EtaRequest, EtaResponse


def compute_eta(request: EtaRequest, provider: BaseProvider) -> EtaResponse:
    return provider.compute_eta(request)

