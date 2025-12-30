from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "logistics-service")
    service_version: str = os.getenv("SERVICE_VERSION", "v0")
    provider: str = os.getenv("LOGISTICS_PROVIDER", "mock")
    osrm_base_url: str = os.getenv("OSRM_BASE_URL", "http://osrm:5000")
    osrm_timeout_seconds: int = int(os.getenv("OSRM_TIMEOUT_SECONDS", "5"))


def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
