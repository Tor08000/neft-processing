from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from neft_logistics_service.schemas import (
    DeviationRequest,
    DeviationResponse,
    EtaRequest,
    EtaResponse,
    Explain,
    RoutePreviewRequest,
    RoutePreviewResponse,
)
from neft_logistics_service.schemas.fleet import (
    FleetListRequest,
    FleetListResponse,
    FleetUpsertRequest,
    FleetUpsertResponse,
)
from neft_logistics_service.schemas.fuel import FuelConsumptionRequest, FuelConsumptionResponse
from neft_logistics_service.schemas.trips import TripCreateRequest, TripCreateResponse, TripStatusResponse


class LogisticsProvider(Protocol):
    name: str

    def fleet_list(self, request: FleetListRequest) -> FleetListResponse: ...

    def fleet_upsert(self, request: FleetUpsertRequest) -> FleetUpsertResponse: ...

    def trip_create(self, request: TripCreateRequest) -> TripCreateResponse: ...

    def trip_get_status(self, trip_id: str) -> TripStatusResponse: ...

    def fuel_get_consumption(self, request: FuelConsumptionRequest) -> FuelConsumptionResponse: ...


class BaseProvider(ABC):
    name: str

    @abstractmethod
    def preview_route(self, request: RoutePreviewRequest) -> RoutePreviewResponse:
        raise NotImplementedError

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


class ProviderUnavailableError(RuntimeError):
    def __init__(self, *, code: str, mode: str, provider: str) -> None:
        super().__init__(code)
        self.code = code
        self.mode = mode
        self.provider = provider


__all__ = ["BaseProvider", "LogisticsProvider", "ProviderUnavailableError"]
