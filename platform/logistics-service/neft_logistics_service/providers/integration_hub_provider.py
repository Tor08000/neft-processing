from __future__ import annotations

import json
import socket
from urllib import error, request as urllib_request

from neft_logistics_service.providers.base import BaseProvider
from neft_logistics_service.schemas import RoutePreviewRequest
from neft_logistics_service.schemas.fleet import FleetListRequest, FleetListResponse, FleetUpsertRequest, FleetUpsertResponse
from neft_logistics_service.schemas.fuel import FuelConsumptionRequest, FuelConsumptionResponse
from neft_logistics_service.schemas.trips import TripCreateRequest, TripCreateResponse, TripStatusResponse
from neft_logistics_service.settings import get_settings
from neft_logistics_service.utils.retry import RetryableError, run_with_retry


class IntegrationHubProvider(BaseProvider):
    name = "integration_hub"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.integration_hub_base_url.rstrip("/")
        self.timeout = self.settings.integration_hub_timeout_sec
        self.internal_token = self.settings.integration_hub_internal_token

    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib_request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        if self.internal_token:
            req.add_header("X-Internal-Token", self.internal_token)

        def _execute() -> dict:
            try:
                with urllib_request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8") or "{}")
                    data.setdefault("request_id", resp.headers.get("X-Request-ID"))
                    return data
            except error.HTTPError as exc:
                if exc.code in {502, 503, 504}:
                    raise RetryableError(f"hub_http_{exc.code}") from exc
                raise
            except (error.URLError, TimeoutError, socket.timeout) as exc:
                raise RetryableError("hub_connection_error") from exc

        return run_with_retry(_execute, max_attempts=self.settings.logistics_retry_max_attempts)

    def fleet_list(self, request: FleetListRequest) -> FleetListResponse:
        data = self._call("POST", "/v1/logistics/fleet/list", request.model_dump())
        return FleetListResponse(**data)

    def fleet_upsert(self, request: FleetUpsertRequest) -> FleetUpsertResponse:
        data = self._call("POST", "/v1/logistics/fleet/upsert", request.model_dump())
        return FleetUpsertResponse(**data)

    def trip_create(self, request: TripCreateRequest) -> TripCreateResponse:
        data = self._call("POST", "/v1/logistics/trips/create", request.model_dump(mode="json"))
        return TripCreateResponse(**data)

    def trip_get_status(self, trip_id: str) -> TripStatusResponse:
        data = self._call("GET", f"/v1/logistics/trips/{trip_id}/status")
        return TripStatusResponse(**data)

    def fuel_get_consumption(self, request: FuelConsumptionRequest) -> FuelConsumptionResponse:
        data = self._call("POST", "/v1/logistics/fuel/consumption", request.model_dump())
        return FuelConsumptionResponse(**data)

    def preview_route(self, request: RoutePreviewRequest):
        raise RuntimeError("compute_provider_unsupported:integration_hub")

    def compute_eta(self, request):
        raise RuntimeError("compute_provider_unsupported:integration_hub")

    def compute_deviation(self, request):
        raise RuntimeError("compute_provider_unsupported:integration_hub")

    def explain_eta(self, request):
        raise RuntimeError("compute_provider_unsupported:integration_hub")

    def explain_deviation(self, request):
        raise RuntimeError("compute_provider_unsupported:integration_hub")
