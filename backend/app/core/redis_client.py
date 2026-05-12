import redis
from app.core.config import get_settings

settings = get_settings()

try:
    if settings.redis_url and settings.redis_url.strip():
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        redis_client.ping()
    else:
        redis_client = None
except Exception:
    redis_client = None


def get_redis():
    return redis_client