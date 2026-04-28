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

        # ---- TOKEN TRACKING ----
        self.last_input_tokens = 0
        self.last_output_tokens = 0

    async def generate(self, prompt: str, config: dict):
        temperature = config.get("temperature", 0)
        max_tokens = config.get("max_tokens", 500)

        response = await self.client.responses.create(
            model=self.deployment,
            input=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # ---- TEXT EXTRACTION ----
        text = ""
        if hasattr(response, "output_text"):
            text = response.output_text
        elif response.output:
            text = "".join(
                [
                    item.content[0].text
                    for item in response.output
                    if item.type == "message"
                ]
            )

        # ---- TOKEN USAGE ----
        usage = getattr(response, "usage", None)

        self.last_input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
        self.last_output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

        return text

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
