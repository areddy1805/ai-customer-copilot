from abc import ABC, abstractmethod


class LLMProvider(ABC):

    @abstractmethod
    async def generate(self, prompt: str, config: dict) -> str:
        pass

    @abstractmethod
    async def stream(self, prompt: str, config: dict):
        pass
