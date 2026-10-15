import time
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from app.router import classify

from app.cache.exact import cache_get, cache_set, is_cacheable
from app.guardrails.base import GuardrailBlocked
from app.guardrails.pipeline import run_input_guardrails
from app.providers.registry import CHAINS, DEFAULT_PROVIDER
from app.reliability.fallback import AllProvidersFailed, run_chain
from app.schemas import ChatRequest, ProviderResponse, Target

app = FastAPI(title="LLM Gateway")


def build_response(res: ProviderResponse, start: float, cache: str, attempts: list, guardrails: list,route=None):
    return {
        "object": "chat.completion",
        "model": res.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": res.text},
                "finish_reason": "stop",
            }
        ],
        "usage": res.usage.model_dump(),
        "x_gateway": {
            "provider": res.provider,
            "cache": cache,  # "hit" | "miss" | "skip"
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "guardrails": guardrails,
            "attempts": attempts,
             "route": route,
        },
    }


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/v1/chains")
async def chains():
    return {a: [t.model_dump() for t in c] for a, c in CHAINS.items()}


@app.post("/v1/guardrails/check")
async def guardrails_check(req: ChatRequest):
    """Debug: run the input guardrails only, no model call."""
    try:
        messages, events = run_input_guardrails(req.messages)
    except GuardrailBlocked as e:
        return {"blocked": True, "event": asdict(e.event)}
    return {
        "blocked": False,
        "messages": [m.model_dump() for m in messages],
        "events": [asdict(e) for e in events],
    }

@app.post("/v1/route/check")
async def route_check(req: ChatRequest):
    """Debug: show which chain a request would be routed to, no model call."""
    return asdict(classify(req))

@app.post("/v1/chat/completions")
async def chat(req: ChatRequest):
    start = time.perf_counter()

    # 1. input guardrails (before cache, so PII never reaches Redis or a provider)
    try:
        messages, events = run_input_guardrails(req.messages)
    except GuardrailBlocked as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "blocked by guardrail",
                "guardrail": e.event.guardrail,
                "reason": e.event.detail,
            },
        )
    req = req.model_copy(update={"messages": messages})
    g_events = [asdict(e) for e in events]

    # 2. cache lookup
    cacheable = is_cacheable(req)
    if cacheable:
        cached = await cache_get(req)
        if cached:
            return build_response(cached, start, "hit", [], g_events)

    # 3. fallback chain
    route = None
    if req.model == "auto":
        decision = classify(req)
        route = asdict(decision)
        chain = CHAINS[decision.chain]
    else:
        chain = CHAINS.get(req.model) or [Target(provider=DEFAULT_PROVIDER, model=req.model)]

    try:
        res, attempts = await run_chain(chain, req)
    except AllProvidersFailed as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "all providers failed", "attempts": e.attempts},
        )

    # 4. save to cache
    if cacheable:
        await cache_set(req, res)

    return build_response(res, start, "miss" if cacheable else "skip", attempts, g_events, route)