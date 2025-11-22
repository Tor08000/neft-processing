import os

CORE_API = os.getenv("CORE_API_URL", "http://core-api:8000")
AI_URL   = os.getenv("AI_URL", "http://ai-service:8000")
TENANT   = int(os.getenv("TENANT_ID", "1"))
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "svc-dev")
