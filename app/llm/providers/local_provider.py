from app.llm.provider import LLMProvider
from app.llm.config import LLMConfig
from app.llm.client import OllamaClient


class LocalProvider(LLMProvider):
    def __init__(self):
        self.client = OllamaClient()

    async def generate(self, prompt: str, config: LLMConfig) -> str:
        return await self.client.generate(
            prompt=prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    async def stream(self, prompt: str, config: LLMConfig):
        async for chunk in self.client.stream(
            prompt=prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        ):
            yield chunk
