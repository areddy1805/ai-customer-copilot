from openai import AsyncAzureOpenAI
from app.llm.provider import LLMProvider
from app.core.config import settings


class AzureProvider(LLMProvider):

    def __init__(self, secret_provider):
        assert settings.AZURE_OPENAI_API_VERSION >= "2025-03-01-preview"
        self.client = AsyncAzureOpenAI(
            api_key=secret_provider.get_secret("AZURE_OPENAI_API_KEY"),
            azure_endpoint=secret_provider.get_secret("AZURE_OPENAI_ENDPOINT"),
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
        self.deployment = secret_provider.get_secret("AZURE_OPENAI_DEPLOYMENT")

    async def generate(self, prompt: str, config: dict) -> str:
        temperature = config.get("temperature", 0)
        max_tokens = config.get("max_tokens", 500)

        response = await self.client.responses.create(
            model=self.deployment,
            input=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        return response.output_text

    async def stream(self, prompt: str, config: dict):
        temperature = config.get("temperature", 0)
        max_tokens = config.get("max_tokens", 500)

        stream = await self.client.responses.stream(
            model=self.deployment,
            input=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta
