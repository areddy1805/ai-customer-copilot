from app.llm.providers.azure_provider import AzureProvider
from app.llm.providers.local_provider import LocalProvider
from app.core.secrets.factory import get_secret_provider
from app.core.config import settings


class LLMService:
    def __init__(self):
        secret_provider = get_secret_provider()

        if settings.LLM_PROVIDER == "azure":
            self.provider = AzureProvider(secret_provider)
        else:
            self.provider = LocalProvider()

    async def generate(
        self,
        prompt: str,
        temperature: float = 0,
        max_tokens: int = 500,
        task: str = "general",
    ) -> str:

        config = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "task": task,
        }

        return await self.provider.generate(prompt, config)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0,
        max_tokens: int = 500,
        task: str = "general",
    ):
        config = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "task": task,
        }

        async for token in self.provider.stream(prompt, config):
            yield token
