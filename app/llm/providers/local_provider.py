from app.llm.provider import LLMProvider
from app.llm.client import OllamaClient


class LocalProvider(LLMProvider):
    def __init__(self):
        self.client = OllamaClient()

    async def generate(self, prompt: str, **kwargs) -> str:
        model = kwargs.get("model")
        return await self.client.generate(model=model, prompt=prompt)

    async def stream(self, prompt: str, **kwargs):
        model = kwargs.get("model")
        async for chunk in self.client.stream(model=model, prompt=prompt):
            yield chunk
