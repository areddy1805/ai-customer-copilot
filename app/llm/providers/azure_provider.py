from openai import AsyncAzureOpenAI
from app.llm.provider import LLMProvider
from app.core.config import settings


class AzureProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncAzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT

    async def generate(self, prompt: str, **kwargs) -> str:
        model = kwargs.get("model", self.deployment)

        response = await self.client.responses.create(
            model=model,
            input=prompt,
            temperature=kwargs.get("temperature", 0.2),
            max_output_tokens=kwargs.get("max_tokens", 512),
        )

        return response.output[0].content[0].text

    async def stream(self, prompt: str, **kwargs):
        model = kwargs.get("model", self.deployment)

        stream = await self.client.responses.stream(
            model=model,
            input=prompt,
            temperature=kwargs.get("temperature", 0.2),
            max_output_tokens=kwargs.get("max_tokens", 512),
        )

        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta
