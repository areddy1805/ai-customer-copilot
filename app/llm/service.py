from app.llm.providers.azure_provider import AzureProvider
from app.llm.providers.local_provider import LocalProvider
from app.core.secrets.factory import get_secret_provider
from app.core.config import settings


class LLMService:
    def __init__(self):
        secret_provider = get_secret_provider()

        self.last_input_tokens = 0
        self.last_output_tokens = 0

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

        result = await self.provider.generate(prompt, config)

        # ---- PROPAGATE TOKENS ----
        self.last_input_tokens = getattr(self.provider, "last_input_tokens", 0)
        self.last_output_tokens = getattr(self.provider, "last_output_tokens", 0)

        return result

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
