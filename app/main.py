# import time
# from dataclasses import asdict
# 
# from fastapi import FastAPI, HTTPException
# from app.router import classify
# 
# from app.cache.exact import cache_get, cache_set, is_cacheable
# from app.guardrails.base import GuardrailBlocked
# from app.guardrails.pipeline import run_input_guardrails
# from app.providers.registry import CHAINS, DEFAULT_PROVIDER
# from app.reliability.fallback import AllProvidersFailed, run_chain
# from app.schemas import ChatRequest, ProviderResponse, Target
# 
# app = FastAPI(title="LLM Gateway")
# 
# 
# def build_response(res: ProviderResponse, start: float, cache: str, attempts: list, guardrails: list,route=None):
    # return {
        # "object": "chat.completion",
        # "model": res.model,
        # "choices": [
            # {
                # "index": 0,
                # "message": {"role": "assistant", "content": res.text},
                # "finish_reason": "stop",
            # }
        # ],
        # "usage": res.usage.model_dump(),
        # "x_gateway": {
            # "provider": res.provider,
            # "cache": cache,  # "hit" | "miss" | "skip"
            # "latency_ms": round((time.perf_counter() - start) * 1000),
            # "guardrails": guardrails,
            # "attempts": attempts,
            #  "route": route,
        # },
    # }
# 
# 
# @app.get("/health")
# async def health():
    # return {"ok": True}
# 
# 
# @app.get("/v1/chains")
# async def chains():
    # return {a: [t.model_dump() for t in c] for a, c in CHAINS.items()}
# 
# 
# @app.post("/v1/guardrails/check")
# async def guardrails_check(req: ChatRequest):
    # """Debug: run the input guardrails only, no model call."""
    # try:
        # messages, events = run_input_guardrails(req.messages)
    # except GuardrailBlocked as e:
        # return {"blocked": True, "event": asdict(e.event)}
    # return {
        # "blocked": False,
        # "messages": [m.model_dump() for m in messages],
        # "events": [asdict(e) for e in events],
    # }
# 
# @app.post("/v1/route/check")
# async def route_check(req: ChatRequest):
    # """Debug: show which chain a request would be routed to, no model call."""
    # return asdict(classify(req))
# 
# @app.post("/v1/chat/completions")
# async def chat(req: ChatRequest):
    # start = time.perf_counter()
# 
# 1. input guardrails (before cache, so PII never reaches Redis or a provider)
    # try:
        # messages, events = run_input_guardrails(req.messages)
    # except GuardrailBlocked as e:
        # raise HTTPException(
            # status_code=400,
            # detail={
                # "error": "blocked by guardrail",
                # "guardrail": e.event.guardrail,
                # "reason": e.event.detail,
            # },
        # )
    # req = req.model_copy(update={"messages": messages})
    # g_events = [asdict(e) for e in events]
# 
    # 2. cache lookup
    # cacheable = is_cacheable(req)
    # if cacheable:
        # cached = await cache_get(req)
        # if cached:
            # return build_response(cached, start, "hit", [], g_events)
# 
    # 3. fallback chain
    # route = None
    # if req.model == "auto":
        # decision = classify(req)
        # route = asdict(decision)
        # chain = CHAINS[decision.chain]
    # else:
        # chain = CHAINS.get(req.model) or [Target(provider=DEFAULT_PROVIDER, model=req.model)]
# 
    # try:
        # res, attempts = await run_chain(chain, req)
    # except AllProvidersFailed as e:
        # raise HTTPException(
            # status_code=502,
            # detail={"error": "all providers failed", "attempts": e.attempts},
        # )
# 
    # 4. save to cache
    # if cacheable:
        # await cache_set(req, res)
# 
    # return build_response(res, start, "miss" if cacheable else "skip", attempts, g_events, route)













import time
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from app.cache.exact import cache_get, cache_set, is_cacheable
from app.cost import compute_cost
from app.db.logger import log_request
from app.db.models import RequestLog
from app.db.session import SessionLocal, init_db
from app.guardrails.base import GuardrailBlocked
from app.guardrails.pipeline import run_input_guardrails
from app.observability import flush, observation
from app.providers.registry import CHAINS, DEFAULT_PROVIDER
from app.reliability.fallback import AllProvidersFailed, run_chain
from app.router import classify
from app.schemas import ChatRequest, ProviderResponse, Target


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception as e:
        print(f"[init_db] failed: {e}")
    yield
    flush()  # send any pending Langfuse events on shutdown


app = FastAPI(title="LLM Gateway", lifespan=lifespan)


def ms_since(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def build_response(
    res: ProviderResponse,
    start: float,
    cache: str,
    attempts: list,
    guardrails: list,
    route=None,
):
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
            "latency_ms": ms_since(start),
            "guardrails": guardrails,
            "attempts": attempts,
            "route": route,
        },
    }


def usage_fields(res, requested_model, route, cache, start, g_events, attempts, hit=False):
    """Fields for a successful request's log row."""
    pt, ct = res.usage.prompt_tokens, res.usage.completion_tokens
    smart = CHAINS.get("smart")
    baseline_model = smart[0].model if smart else res.model
    return dict(
        status="ok",
        requested_model=requested_model,
        resolved_model=res.model,
        provider=res.provider,
        chain=route["chain"] if route else None,
        cache=cache,
        prompt_tokens=pt,
        completion_tokens=ct,
        cost_usd=0.0 if hit else compute_cost(res.model, pt, ct),
        baseline_cost_usd=compute_cost(baseline_model, pt, ct),
        latency_ms=ms_since(start),
        guardrails=g_events,
        attempts=attempts,
    )


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


@app.get("/v1/stats")
async def stats():
    async with SessionLocal() as s:
        total = (
            await s.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(RequestLog.cost_usd), 0),
                    func.coalesce(func.sum(RequestLog.baseline_cost_usd), 0),
                    func.coalesce(func.avg(RequestLog.latency_ms), 0),
                )
            )
        ).one()
        by_chain = (
            await s.execute(select(RequestLog.chain, func.count()).group_by(RequestLog.chain))
        ).all()
        by_cache = (
            await s.execute(select(RequestLog.cache, func.count()).group_by(RequestLog.cache))
        ).all()
        by_status = (
            await s.execute(select(RequestLog.status, func.count()).group_by(RequestLog.status))
        ).all()

    requests, cost, baseline, avg_latency = total
    return {
        "requests": requests,
        "total_cost_usd": round(float(cost), 6),
        "baseline_cost_usd": round(float(baseline), 6),
        "saved_usd": round(float(baseline - cost), 6),
        "avg_latency_ms": round(float(avg_latency)),
        "by_chain": {c or "direct": n for c, n in by_chain},
        "by_cache": dict(by_cache),
        "by_status": dict(by_status),
    }


@app.post("/v1/chat/completions")
async def chat(req: ChatRequest, background: BackgroundTasks):
    # One root trace per request; the real work happens in _chat.
    with observation("gateway-request") as root:
        out = await _chat(req, background, root)
        root.update(
            output=out["choices"][0]["message"]["content"],
            metadata=out["x_gateway"],
        )
        return out


async def _chat(req: ChatRequest, background: BackgroundTasks, root):
    start = time.perf_counter()
    requested_model = req.model

    # 1. input guardrails (before cache, so PII never reaches Redis, a provider, or Langfuse)
    try:
        with observation("input-guardrails", as_type="guardrail") as gobs:
            messages, events = run_input_guardrails(req.messages)
            gobs.update(output={"events": [asdict(e) for e in events]})
    except GuardrailBlocked as e:
        root.update(
            level="WARNING",
            status_message=f"blocked by {e.event.guardrail}",
            metadata={"requested_model": requested_model},
        )
        background.add_task(
            log_request,
            status="blocked_input",
            requested_model=requested_model,
            latency_ms=ms_since(start),
            guardrails=[asdict(e.event)],
        )
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

    # Only the redacted messages are ever sent to Langfuse.
    root.update(
        input=[m.model_dump() for m in messages],
        metadata={"requested_model": requested_model},
    )

    # 2. cache lookup
    cacheable = is_cacheable(req)
    if cacheable:
        with observation("cache-lookup") as cobs:
            cached = await cache_get(req)
            cobs.update(output={"hit": bool(cached)})
        if cached:
            background.add_task(
                log_request,
                **usage_fields(cached, requested_model, None, "hit", start, g_events, [], hit=True),
            )
            return build_response(cached, start, "hit", [], g_events)

    # 3. router + fallback chain
    route = None
    if req.model == "auto":
        with observation("router") as robs:
            decision = classify(req)
            route = asdict(decision)
            robs.update(output=route)
        chain = CHAINS[decision.chain]
    else:
        chain = CHAINS.get(req.model) or [Target(provider=DEFAULT_PROVIDER, model=req.model)]

    with observation(
        "llm-call",
        as_type="generation",
        model=chain[0].model,
        input=[m.model_dump() for m in req.messages],
        model_parameters={"temperature": req.temperature, "max_tokens": req.max_tokens},
    ) as gen:
        try:
            res, attempts = await run_chain(chain, req)
        except AllProvidersFailed as e:
            gen.update(
                level="ERROR",
                status_message="all providers failed",
                metadata={"attempts": jsonable_encoder(e.attempts)},
            )
            background.add_task(
                log_request,
                status="failed",
                requested_model=requested_model,
                chain=route["chain"] if route else None,
                latency_ms=ms_since(start),
                guardrails=g_events,
                attempts=e.attempts,
            )
            raise HTTPException(
                status_code=502,
                detail={"error": "all providers failed", "attempts": e.attempts},
            )

        pt, ct = res.usage.prompt_tokens, res.usage.completion_tokens
        gen.update(
            model=res.model,  # the model that actually answered (after any fallback)
            output=res.text,
            usage_details={"input_tokens": pt, "output_tokens": ct},
            cost_details={"total": compute_cost(res.model, pt, ct)},
            metadata={
                "provider": res.provider,
                "chain": route["chain"] if route else None,
                "attempts": jsonable_encoder(attempts),
            },
        )

    # 4. save to cache
    if cacheable:
        await cache_set(req, res)

    cache_state = "miss" if cacheable else "skip"
    background.add_task(
        log_request,
        **usage_fields(res, requested_model, route, cache_state, start, g_events, attempts),
    )
    return build_response(res, start, cache_state, attempts, g_events, route)