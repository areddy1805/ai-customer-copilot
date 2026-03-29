from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    async def stream(self, prompt: str, **kwargs):
        pass
