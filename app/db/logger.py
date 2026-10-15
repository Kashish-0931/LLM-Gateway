from fastapi.encoders import jsonable_encoder

from app.db.models import RequestLog
from app.db.session import SessionLocal


async def log_request(**fields):
    """Never raises: a logging failure must not break a user request."""
    try:
        # makes dataclasses / pydantic objects safe to store as JSON
        for key in ("guardrails", "attempts"):
            if key in fields:
                fields[key] = jsonable_encoder(fields[key])
        async with SessionLocal() as s:
            s.add(RequestLog(**fields))
            await s.commit()
    except Exception as e:
        print(f"[log_request] failed: {e}")