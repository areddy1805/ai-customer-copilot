from app.llm.models import TaskType
from app.llm.prompts import build_prompt
from app.llm.config import LLM_CONFIG_MAP

from app.llm.providers.azure_provider import AzureProvider
from app.llm.providers.local_provider import LocalProvider
from app.core.secrets.factory import get_secret_provider

from app.utils.retry import retry
import asyncio


class LLMService:
    def __init__(self):
        secret_provider = get_secret_provider()

        # Primary + fallback providers
        self.azure = AzureProvider(secret_provider=secret_provider)
        self.local = LocalProvider()

    async def generate(self, task: TaskType, query: str, context: str = "") -> str:
        prompt = build_prompt(task=task, query=query, context=context)
        config = LLM_CONFIG_MAP[task]

        # ---------- AZURE (PRIMARY) ----------
        try:

            async def safe_azure():
                return await asyncio.wait_for(
                    retry(self.azure.generate)(prompt, config), timeout=10
                )

            response = await safe_azure()

        # ---------- FALLBACK (LOCAL) ----------
        except Exception:
            response = await self.local.generate(prompt, config)

        # ---------- POST VALIDATION ----------
        if not response or len(response.strip()) < 5:
            return "Please provide more specific details."

        if task == TaskType.GENERAL and len(response.split()) > 40:
            return "Please provide more specific details."

        return response

    async def generate_stream(self, task: TaskType, query: str, context: str = ""):
        prompt = build_prompt(task=task, query=query, context=context)
        config = LLM_CONFIG_MAP[task]

        # ---------- AZURE (PRIMARY) ----------
        try:
            async for token in self.azure.stream(prompt, config):
                yield token

        # ---------- FALLBACK (LOCAL) ----------
        except Exception:
            async for token in self.local.stream(prompt, config):
                yield token
