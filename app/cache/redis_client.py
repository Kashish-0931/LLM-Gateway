import redis.asyncio as redis
from app.config import settings

r = redis.from_url(settings.redis_url, decode_responses=True)