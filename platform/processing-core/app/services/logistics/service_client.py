from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from neft_shared.settings import get_settings


@dataclass(frozen=True)
class ETAResult:
    eta_minutes: int
    confidence: float
    provider: str
    explain: dict[str, Any]


@dataclass(frozen=True)
class DeviationResult:
    deviation_meters: int
    is_violation: bool
    confidence: float
    explain: dict[str, Any]


@dataclass(frozen=True)
class RoutePreviewPoint:
    lat: float
    lon: float


@dataclass(frozen=True)
class RoutePreviewResult:
    provider: str
    geometry: tuple[RoutePreviewPoint, ...]
    distance_km: float
    eta_minutes: int
    confidence: float
    computed_at: datetime
    degraded: bool
    degradation_reason: str | None


class LogisticsServiceClient:
    def __init__(self, *, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (
            base_url or os.getenv("LOGISTICS_SERVICE_URL", settings.LOGISTICS_SERVICE_URL)
        ).rstrip("/")
        self.internal_token = os.getenv("LOGISTICS_INTERNAL_TOKEN", "").strip()
        self.timeout = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0)

    def compute_eta(self, payload: dict[str, Any]) -> ETAResult:
        return self._post("/v1/eta", payload, parse=self._parse_eta)

    def compute_deviation(self, payload: dict[str, Any]) -> DeviationResult:
        return self._post("/v1/deviation", payload, parse=self._parse_deviation)

    def explain(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/v1/explain", payload, parse=lambda data: data["explain"])

    def preview_route(self, payload: dict[str, Any]) -> RoutePreviewResult:
        headers = {"X-Internal-Token": self.internal_token} if self.internal_token else None
        return self._post("/api/int/v1/routes/preview", payload, parse=self._parse_preview, headers=headers)

    def fuel_consumption(self, payload: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if self.internal_token:
            headers["X-Internal-Token"] = self.internal_token
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return self._post("/v1/fuel/consumption", payload, parse=lambda data: data, headers=headers or None)

    def _post(self, path: str, payload: dict[str, Any], *, parse, headers: dict[str, str] | None = None):
        last_error: Exception | None = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    request_kwargs: dict[str, Any] = {"json": payload}
                    if headers:
                        request_kwargs["headers"] = headers
                    response = client.post(f"{self.base_url}{path}", **request_kwargs)
                response.raise_for_status()
                data = response.json()
                return parse(data)
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise RuntimeError("logistics_service_error") from exc
        raise RuntimeError("logistics_service_unreachable") from last_error

    @staticmethod
    def _parse_eta(data: dict[str, Any]) -> ETAResult:
        return ETAResult(
            eta_minutes=int(data["eta_minutes"]),
            confidence=float(data["confidence"]),
            provider=str(data["provider"]),
            explain=data.get("explain") or {},
        )

    @staticmethod
    def _parse_deviation(data: dict[str, Any]) -> DeviationResult:
        return DeviationResult(
            deviation_meters=int(data["deviation_meters"]),
            is_violation=bool(data["is_violation"]),
            confidence=float(data["confidence"]),
            explain=data.get("explain") or {},
        )

    @staticmethod
    def _parse_preview(data: dict[str, Any]) -> RoutePreviewResult:
        return RoutePreviewResult(
            provider=str(data["provider"]),
            geometry=tuple(
                RoutePreviewPoint(lat=float(point["lat"]), lon=float(point["lon"]))
                for point in data.get("geometry") or []
            ),
            distance_km=float(data["distance_km"]),
            eta_minutes=int(data["eta_minutes"]),
            confidence=float(data["confidence"]),
            computed_at=_parse_datetime(str(data["computed_at"])),
            degraded=bool(data["degraded"]),
            degradation_reason=str(data["degradation_reason"]) if data.get("degradation_reason") else None,
        )


def _parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    return datetime.fromisoformat(value)


__all__ = [
    "DeviationResult",
    "ETAResult",
    "LogisticsServiceClient",
    "RoutePreviewPoint",
    "RoutePreviewResult",
]
