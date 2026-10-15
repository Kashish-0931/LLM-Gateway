from abc import ABC, abstractmethod
from app.schemas import ChatRequest, ProviderResponse


class Provider(ABC):
    name: str

    @abstractmethod
    async def complete(self, req: ChatRequest) -> ProviderResponse: ...