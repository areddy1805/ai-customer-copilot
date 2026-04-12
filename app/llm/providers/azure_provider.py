from openai import AsyncAzureOpenAI
from app.llm.provider import LLMProvider
from app.llm.config import LLMConfig
from app.core.config import settings


class AzureProvider(LLMProvider):

    def __init__(self, secret_provider):
        self.secret_provider = secret_provider

        self.client = AsyncAzureOpenAI(
            api_key=self.secret_provider.get_secret("AZURE_OPENAI_API_KEY"),
            azure_endpoint=self.secret_provider.get_secret("AZURE_OPENAI_ENDPOINT"),
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )

        self.deployment = self.secret_provider.get_secret("AZURE_OPENAI_DEPLOYMENT")

    async def generate(self, prompt: str, config: LLMConfig) -> str:
        response = await self.client.responses.create(
            model=self.deployment,
            input=prompt,
            temperature=config.temperature,
            max_output_tokens=config.max_tokens,
        )
        return response.output[0].content[0].text

    async def stream(self, prompt: str, config: LLMConfig):
        stream = await self.client.responses.stream(
            model=self.deployment,
            input=prompt,
            temperature=config.temperature,
            max_output_tokens=config.max_tokens,
        )

        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta
