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

        try:
            response = self.client.generate(model=model, prompt=prompt)

            # -------- EMPTY RESPONSE HANDLING --------
            if not response or not response.strip():
                return "I'm unable to generate a resposne at the moment."
            return response
        except Exception as e:
            # -------- FAIL-SAFE RESPONSE --------
            return "I'm experiencing technical difficulties. Please try again shortly."

    def generate_stream(self, task: TaskType, query: str, context: str = ""):
        """
        Streaming version of LLM call
        """

        model = get_model_for_task(task)

        prompt = build_prompt(task=task, query=query, context=context)

        try:
            for token in self.client.generate_stream(model=model, prompt=prompt):
                yield token

        except Exception:
            # -------- STREAM FAIL-SAFE --------
            yield "I'm experiencing technical difficulties. Please try again later."
