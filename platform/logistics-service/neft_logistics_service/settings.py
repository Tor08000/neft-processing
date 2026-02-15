from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "logistics-service")
    service_version: str = os.getenv("SERVICE_VERSION", "v0")
    app_env: str = os.getenv("APP_ENV", "prod").lower()
    use_mock_logistics: bool = _env_bool("USE_MOCK_LOGISTICS", "0")
    osrm_base_url: str = os.getenv("OSRM_BASE_URL", "http://osrm:5000")
    osrm_timeout_seconds: int = int(os.getenv("OSRM_TIMEOUT_SECONDS", "5"))

    @property
    def provider(self) -> str:
        configured_provider = os.getenv("LOGISTICS_PROVIDER")
        if configured_provider:
            return configured_provider
        return "mock" if self.use_mock_logistics else "osrm"


def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
