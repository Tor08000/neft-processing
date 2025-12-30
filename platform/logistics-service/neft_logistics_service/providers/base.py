from __future__ import annotations

from abc import ABC, abstractmethod

from neft_logistics_service.schemas import DeviationRequest, DeviationResponse, EtaRequest, EtaResponse, Explain


class BaseProvider(ABC):
    name: str

    @abstractmethod
    def compute_eta(self, request: EtaRequest) -> EtaResponse:
        raise NotImplementedError

    @abstractmethod
    def compute_deviation(self, request: DeviationRequest) -> DeviationResponse:
        raise NotImplementedError

    @abstractmethod
    def explain_eta(self, request: EtaRequest) -> Explain:
        raise NotImplementedError

    @abstractmethod
    def explain_deviation(self, request: DeviationRequest) -> Explain:
        raise NotImplementedError


__all__ = ["BaseProvider"]
