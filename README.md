# LLM Gateway

An OpenAI-compatible LLM gateway built from scratch with FastAPI. It sits between your app and model providers (Hugging Face, Ollama, Groq, or any OpenAI-style API) and adds automatic fallbacks, response caching, input guardrails, and Langfuse tracing. Providers and model chains are set in a YAML config, so swapping a model needs no code changes.

If a model fails, the gateway retries with backoff and moves down the fallback chain, and a circuit breaker skips targets that keep failing. Prompts are checked for injection attempts, and PII (emails, phones, cards, Aadhaar, PAN) is redacted before anything reaches Redis or a provider. Repeated requests at temperature 0 are served from a Redis cache.

**Stack:** Python, FastAPI, httpx, Redis, Langfuse, pytest
**Run:** `pip install -r requirements.txt`, copy `.env.example` to `.env`, then `uvicorn app.main:app --reload` and open `/docs`.
