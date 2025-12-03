import uuid
from neft_shared.settings import get_settings
from redis import Redis

def get_correlation_id() -> str:
    return str(uuid.uuid4())

def get_redis() -> Redis:
    cfg = get_settings()
    return Redis.from_url(cfg.redis_url, decode_responses=True)

def get_current_user():
    return {"id": 1, "email": "admin@neft.local"}
