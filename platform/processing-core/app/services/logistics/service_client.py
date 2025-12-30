from __future__ import annotations

from dataclasses import dataclass
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


class LogisticsServiceClient:
    def __init__(self, *, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.LOGISTICS_SERVICE_URL).rstrip("/")
        self.timeout = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0)

    def compute_eta(self, payload: dict[str, Any]) -> ETAResult:
        return self._post("/v1/eta", payload, parse=self._parse_eta)

    def compute_deviation(self, payload: dict[str, Any]) -> DeviationResult:
        return self._post("/v1/deviation", payload, parse=self._parse_deviation)

    def explain(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/v1/explain", payload, parse=lambda data: data["explain"])

    def _post(self, path: str, payload: dict[str, Any], *, parse):
        last_error: Exception | None = None
        for _ in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(f"{self.base_url}{path}", json=payload)
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


__all__ = ["DeviationResult", "ETAResult", "LogisticsServiceClient"]
