from app.llm.provider_factory import get_llm_provider
from app.llm.models import get_model_for_task, TaskType
from app.llm.prompts import build_prompt


class LLMService:
    def __init__(self):
        self.provider = get_llm_provider()

    async def generate(self, task: TaskType, query: str, context: str = "") -> str:
        model = get_model_for_task(task)
        prompt = build_prompt(task=task, query=query, context=context)

        try:
            response = await self.provider.generate(
                prompt,
                model=model,
                temperature=0.2,
                max_tokens=512,
            )

            if not response or len(response.strip()) < 5:
                return "Please provide more specific details."

            if task == TaskType.GENERAL and len(response.split()) > 40:
                return "Please provide more specific details."

            return response

        except Exception:
            return "Please provide more specific details."

    async def generate_stream(self, task: TaskType, query: str, context: str = ""):
        model = get_model_for_task(task)
        prompt = build_prompt(task=task, query=query, context=context)

        try:
            async for token in self.provider.stream(
                prompt,
                model=model,
                temperature=0.2,
                max_tokens=512,
            ):
                yield token

        except Exception:
            yield "Please provide more specific details."
