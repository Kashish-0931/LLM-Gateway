import asyncio

import httpx

from app.providers.registry import PROVIDERS
from app.reliability.circuitbreaker import CircuitBreaker
from app.schemas import ChatRequest, ProviderResponse, Target

breaker = CircuitBreaker(threshold=3, cooldown=30)


class AllProvidersFailed(Exception):
    def __init__(self, attempts: list[dict]):
        self.attempts = attempts


def is_retryable(e: Exception) -> bool:
    """Retry on timeouts, connection errors, 429 and 5xx. Never on 400/401/404."""
    if isinstance(e, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(e, httpx.HTTPStatusError):
        s = e.response.status_code
        return s == 429 or s >= 500
    return False


def describe(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}: {e.response.text[:150]}"
    return type(e).__name__


async def call_with_retry(provider, req: ChatRequest, retries: int = 2, base_delay: float = 0.5):
    for attempt in range(retries + 1):
        try:
            return await provider.complete(req)
        except Exception as e:
            if not is_retryable(e) or attempt == retries:
                raise
            await asyncio.sleep(base_delay * 2**attempt)  # 0.5s, then 1s


async def run_chain(chain: list[Target], req: ChatRequest) -> tuple[ProviderResponse, list[dict]]:
    attempts: list[dict] = []

    for t in chain:
        key = f"{t.provider}:{t.model}"

        if breaker.is_open(key):
            attempts.append({"target": key, "status": "skipped_circuit_open"})
            continue

        provider = PROVIDERS[t.provider]
        r = req.model_copy(update={"model": t.model})
        try:
            res = await call_with_retry(provider, r)
            breaker.record_success(key)
            attempts.append({"target": key, "status": "ok"})
            return res, attempts
        except Exception as e:
            breaker.record_failure(key)
            attempts.append({"target": key, "status": "failed", "error": describe(e)})

    raise AllProvidersFailed(attempts)