from app.llm.provider_factory import get_llm_provider
from app.llm.models import TaskType
from app.llm.prompts import build_prompt
from app.llm.config import LLM_CONFIG_MAP


class LLMService:
    def __init__(self):
        self.provider = get_llm_provider()

    async def generate(self, task: TaskType, query: str, context: str = "") -> str:
        prompt = build_prompt(task=task, query=query, context=context)
        config = LLM_CONFIG_MAP[task]

        try:
            response = await self.provider.generate(prompt, config)

            if not response or len(response.strip()) < 5:
                return "Please provide more specific details."

            if task == TaskType.GENERAL and len(response.split()) > 40:
                return "Please provide more specific details."

            return response

        except Exception:
            return "Please provide more specific details."

    async def generate_stream(self, task: TaskType, query: str, context: str = ""):
        prompt = build_prompt(task=task, query=query, context=context)
        config = LLM_CONFIG_MAP[task]

        try:
            async for token in self.provider.stream(prompt, config):
                yield token

        except Exception:
            yield "Please provide more specific details."
