import os

from neft_shared.settings import get_settings

settings = get_settings()

CORE_API = os.getenv("CORE_API_URL", "http://core-api:8000")
AI_URL = os.getenv("AI_URL", "http://ai-service:8000")
TENANT = int(os.getenv("TENANT_ID", "1"))
REDIS_URL = settings.redis_url
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "svc-dev")
