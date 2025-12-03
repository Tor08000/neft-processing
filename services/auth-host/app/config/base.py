from __future__ import annotations

import os
from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    env: str = os.getenv("NEFT_ENV", "local")
    enable_tracing: bool = True
    otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    service_name: str = os.getenv("SERVICE_NAME", "auth-host")

    class Config:
        env_prefix = "NEFT_"
        env_file = os.getenv("ENV_FILE", None)


def load_config() -> BaseConfig:
    return BaseConfig()
