import asyncio
from sqlalchemy import text
from app.config import settings
from app.db.session import engine
from app.cache.redis_client import r


async def main():
    # check .env loaded
    print("DATABASE_URL set:", bool(settings.database_url))
    print("REDIS_URL set:   ", bool(settings.redis_url))
    print("HF_TOKEN set:    ", bool(settings.hf_token))
    print("-" * 30)

    try:
        async with engine.connect() as c:
            print("postgres:", (await c.execute(text("select 1"))).scalar())
    except Exception as e:
        print("postgres FAILED:", repr(e)[:300])

    try:
        await r.set("ping", "pong", ex=10)
        print("redis:", await r.get("ping"))
    except Exception as e:
        print("redis FAILED:", repr(e)[:300])

    await engine.dispose()
    await r.aclose()


asyncio.run(main())