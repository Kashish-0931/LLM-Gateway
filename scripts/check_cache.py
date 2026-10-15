import asyncio

from app.cache.exact import cache_get, cache_set, make_key
from app.cache.redis_client import r
from app.schemas import ChatRequest, Message, ProviderResponse, Usage


async def main():
    req = ChatRequest(
        model="fast",
        messages=[Message(role="user", content="cache test")],
        temperature=0,
    )
    res = ProviderResponse(
        text="saved answer",
        usage=Usage(prompt_tokens=3, completion_tokens=2),
        provider="test",
        model="test-model",
    )

    print("1. before set:", await cache_get(req))          # expect None
    await cache_set(req, res)
    got = await cache_get(req)
    print("2. after set: ", got.text if got else None)     # expect "saved answer"

    other = req.model_copy(update={"messages": [Message(role="user", content="different")]})
    print("3. different prompt:", await cache_get(other))  # expect None

    print("4. ttl (sec):", await r.ttl(make_key(req)))     # expect ~3600

    await r.delete(make_key(req))
    print("5. after delete:", await cache_get(req))        # expect None
    await r.aclose()


asyncio.run(main())