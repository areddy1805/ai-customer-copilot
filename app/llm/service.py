from app.llm.client import OllamaClient
from app.llm.models import get_model_for_task, TaskType
from app.llm.prompts import build_prompt
import threading


class LLMService:
    def __init__(self):
        self.client = OllamaClient()
        self._lock = threading.Lock()

    def generate(self, task: TaskType, query: str, context: str = "") -> str:
        model = get_model_for_task(task)
        prompt = build_prompt(task=task, query=query, context=context)

        try:
            with self._lock:
                response = self.client.generate(model=model, prompt=prompt)

            if not response or len(response.strip()) < 5:
                return "Please provide more specific details."

            if task == TaskType.GENERAL and len(response.split()) > 40:
                return "Please provide more specific details."

            return response

        except Exception:
            return "Please provide more specific details."

    def generate_stream(self, task: TaskType, query: str, context: str = ""):
        model = get_model_for_task(task)
        prompt = build_prompt(task=task, query=query, context=context)

        try:
            with self._lock:
                for token in self.client.generate_stream(model=model, prompt=prompt):
                    yield token

        except Exception:
            yield "Please provide more specific details."
