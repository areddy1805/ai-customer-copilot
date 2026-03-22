from app.llm.client import OllamaClient
from app.llm.models import get_model_for_task, TaskType
from app.llm.prompts import build_prompt


class LLMService:
    def __init__(self):
        self.client = OllamaClient()

    def generate(self, task: TaskType, query: str, context: str = "") -> str:
        """
        Main entry point for non-streaming LLM calls
        """

        model = get_model_for_task(task)

        prompt = build_prompt(task=task, query=query, context=context)

        response = self.client.generate(model=model, prompt=prompt)

        return response

    def generate_stream(self, task: TaskType, query: str, context: str = ""):
        """
        Streaming version of LLM call
        """

        model = get_model_for_task(task)

        prompt = build_prompt(task=task, query=query, context=context)

        return self.client.generate_stream(model=model, prompt=prompt)
