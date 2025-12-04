from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable

from neft_shared.settings import Settings as SharedSettings


def _env_or_default(key: str, default: str, *, fallback_keys: Iterable[str] = ()) -> str:
    for candidate in (key, *fallback_keys):
        value = os.getenv(candidate)
        if value is not None:
            return value
    return default


def _roles_env(key: str, default: list[str], *, fallback_keys: Iterable[str] = ()) -> list[str]:
    for candidate in (key, *fallback_keys):
        raw = os.getenv(candidate)
        if raw:
            return [part.strip() for part in raw.split(",") if part.strip()]
    return default


@dataclass
class Settings(SharedSettings):
    core_api: str = _env_or_default("CORE_API_URL", "http://core-api:8000/api/v1")
    ai_url: str = _env_or_default("AI_URL", "http://ai-service:8000")
    tenant_id: int = int(_env_or_default("TENANT_ID", "1"))
    service_token: str = _env_or_default("SERVICE_TOKEN", "svc-dev")

    demo_client_email: str = _env_or_default(
        "NEFT_DEMO_CLIENT_EMAIL",
        "client@neft.local",
        fallback_keys=("DEMO_CLIENT_EMAIL",),
    )
    demo_client_password: str = _env_or_default(
        "NEFT_DEMO_CLIENT_PASSWORD", "client", fallback_keys=("DEMO_CLIENT_PASSWORD",)
    )
    demo_client_id: str = _env_or_default(
        "NEFT_DEMO_CLIENT_ID", "demo-client", fallback_keys=("DEMO_CLIENT_ID",)
    )
    demo_client_full_name: str = _env_or_default(
        "NEFT_DEMO_CLIENT_FULL_NAME",
        "Demo Client",
        fallback_keys=("DEMO_CLIENT_FULL_NAME",),
    )
    demo_client_uuid: str = _env_or_default(
        "NEFT_DEMO_CLIENT_UUID",
        "00000000-0000-0000-0000-000000000001",
        fallback_keys=("DEMO_CLIENT_UUID",),
    )

    demo_admin_email: str = _env_or_default(
        "NEFT_DEMO_ADMIN_EMAIL",
        "admin@example.com",
        fallback_keys=("DEMO_ADMIN_EMAIL",),
    )
    demo_admin_password: str = _env_or_default(
        "NEFT_DEMO_ADMIN_PASSWORD", "admin", fallback_keys=("DEMO_ADMIN_PASSWORD",)
    )
    demo_admin_full_name: str = _env_or_default(
        "NEFT_DEMO_ADMIN_FULL_NAME",
        "Platform Admin",
        fallback_keys=("DEMO_ADMIN_FULL_NAME",),
    )
    demo_admin_roles: list[str] = field(
        default_factory=lambda: _roles_env(
            "NEFT_DEMO_ADMIN_ROLES", ["ADMIN", "SUPERADMIN"], fallback_keys=("DEMO_ADMIN_ROLES",)
        )
    )


def get_settings() -> Settings:
    return Settings()


settings = get_settings()

CORE_API = settings.core_api.rstrip("/")
AI_URL = settings.ai_url
TENANT = settings.tenant_id
REDIS_URL = settings.redis_url
SERVICE_TOKEN = settings.service_token
