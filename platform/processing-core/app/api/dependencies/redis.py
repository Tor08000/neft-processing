from neft_shared.settings import get_settings
from redis import Redis


def get_redis() -> Redis:
    cfg = get_settings()
    return Redis.from_url(cfg.redis_url, decode_responses=True)
