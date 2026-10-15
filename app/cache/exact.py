import hashlib
import json

from app.cache.redis_client import r
from app.schemas import ChatRequest, ProviderResponse

PREFIX = "cache:v1:"
TTL_SECONDS = 3600  # 1 hour


def make_key(req: ChatRequest) -> str:
    payload = {
        "model": req.model,  # the alias the client asked for
        "messages": [m.model_dump() for m in req.messages],
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return PREFIX + hashlib.sha256(raw.encode()).hexdigest()


def is_cacheable(req: ChatRequest) -> bool:
    return req.temperature == 0


async def cache_get(req: ChatRequest) -> ProviderResponse | None:
    try:
        data = await r.get(make_key(req))
    except Exception:
        return None  # Redis problem: act like a miss
    if not data:
        return None
    return ProviderResponse.model_validate_json(data)


async def cache_set(req: ChatRequest, res: ProviderResponse) -> None:
    if not res.text.strip():
        return  # don't cache empty answers
    try:
        await r.set(make_key(req), res.model_dump_json(), ex=TTL_SECONDS)
    except Exception:
        pass  # never break a request because the cache failed