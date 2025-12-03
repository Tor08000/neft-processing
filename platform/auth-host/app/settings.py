from __future__ import annotations

import os
from dataclasses import dataclass

from neft_shared.settings import Settings as SharedSettings


@dataclass
class Settings(SharedSettings):
    core_api: str = os.getenv("CORE_API_URL", "http://core-api:8000/api/v1")
    ai_url: str = os.getenv("AI_URL", "http://ai-service:8000")
    tenant_id: int = int(os.getenv("TENANT_ID", "1"))
    service_token: str = os.getenv("SERVICE_TOKEN", "svc-dev")

    demo_client_email: str = os.getenv("DEMO_CLIENT_EMAIL", "client@neft.local")
    demo_client_password: str = os.getenv("DEMO_CLIENT_PASSWORD", "client")
    demo_client_id: str = os.getenv("DEMO_CLIENT_ID", "demo-client")
    demo_client_full_name: str = os.getenv("DEMO_CLIENT_FULL_NAME", "Demo Client")
    demo_client_uuid: str = os.getenv("DEMO_CLIENT_UUID", "00000000-0000-0000-0000-000000000001")


def get_settings() -> Settings:
    return Settings()


settings = get_settings()

CORE_API = settings.core_api.rstrip("/")
AI_URL = settings.ai_url
TENANT = settings.tenant_id
REDIS_URL = settings.redis_url
SERVICE_TOKEN = settings.service_token
