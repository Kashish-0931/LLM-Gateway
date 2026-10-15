from pydantic import BaseModel


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    temperature: float = 1.0
    max_tokens: int = 512


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ProviderResponse(BaseModel):
    text: str
    usage: Usage
    provider: str
    model: str
    
class Target(BaseModel):
    """One step in a fallback chain: which provider, which model."""
    provider: str
    model: str    