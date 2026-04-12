from abc import ABC, abstractmethod
from app.llm.config import LLMConfig


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, config: LLMConfig) -> str:
        pass

    @abstractmethod
    async def stream(self, prompt: str, config: LLMConfig):
        pass
