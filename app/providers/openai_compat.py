import httpx
from app.providers.base import Provider
from app.schemas import ChatRequest, ProviderResponse, Usage


class OpenAICompatProvider(Provider):
    def __init__(self, name: str, base_url: str, api_key: str = ""):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def complete(self, req: ChatRequest) -> ProviderResponse:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = {
            "model": req.model,
            "messages": [m.model_dump() for m in req.messages],
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=body
            )
            r.raise_for_status()
            d = r.json()

        u = d.get("usage") or {}
        return ProviderResponse(
            text=d["choices"][0]["message"]["content"] or "",
            usage=Usage(
                prompt_tokens=u.get("prompt_tokens", 0),
                completion_tokens=u.get("completion_tokens", 0),
            ),
            provider=self.name,
            model=d.get("model", req.model),
        )