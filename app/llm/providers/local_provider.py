from app.llm.provider import LLMProvider
from app.llm.client import OllamaClient
from app.llm.models import get_model_for_task


class LocalProvider(LLMProvider):
    def __init__(self):
        self.client = OllamaClient()

    async def generate(self, prompt: str, config: dict) -> str:
        model = get_model_for_task(config.get("task", "general"))

        return await self.client.generate(
            prompt=prompt,
            model=model,
            temperature=config.get("temperature", 0),
            max_tokens=config.get("max_tokens", 200),
        )

    async def stream(self, prompt: str, config: dict):
        model = get_model_for_task(config.get("task", "general"))

        async for chunk in self.client.stream(
            prompt=prompt,
            model=model,
            temperature=config.get("temperature", 0),
            max_tokens=config.get("max_tokens", 200),
        ):
            yield chunk
