from app.llm.provider import LLMProvider
from app.llm.client import OllamaClient
from app.llm.models import get_model_for_task


class LocalProvider(LLMProvider):
    def __init__(self):
        self.client = OllamaClient()

        # ---- TOKEN TRACKING ----
        self.last_input_tokens = 0
        self.last_output_tokens = 0

    async def generate(self, prompt: str, config: dict):
        model = get_model_for_task(config.get("task", "general"))

        text = await self.client.generate(
            prompt=prompt,
            model=model,
            temperature=config.get("temperature", 0),
            max_tokens=config.get("max_tokens", 200),
        )

        # ---- ESTIMATION ----
        self.last_input_tokens = len(prompt.split())
        self.last_output_tokens = len(text.split())

        return text

    async def stream(self, prompt: str, config: dict):
        model = get_model_for_task(config.get("task", "general"))

        async for chunk in self.client.stream(
            prompt=prompt,
            model=model,
            temperature=config.get("temperature", 0),
            max_tokens=config.get("max_tokens", 200),
        ):
            yield chunk
