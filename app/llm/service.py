from app.llm.client import OllamaClient
from app.llm.models import get_model_for_task, TaskType
from app.llm.prompts import build_prompt
import threading
from app.cache.llm_cache import LLMCache


class LLMService:
    def __init__(self):
        self.client = OllamaClient()
        self._lock = threading.Lock()
        self.cache = LLMCache()

    # -------- CORE GENERATE (WITH CACHE) --------
    def generate(self, task: TaskType, query: str, context: str = "") -> str:
        model = get_model_for_task(task)
        prompt = build_prompt(task=task, query=query, context=context)

        payload = {
            "task": task.value,
            "query": query,
            "context": context,
            "model": model,
        }

        # -------- CACHE HIT --------
        cached = self.cache.get(payload)
        if cached:
            print("LLM CACHE HIT")
            return cached

        try:
            with self._lock:
                response = self.client.generate(model=model, prompt=prompt)

            if not response or len(response.strip()) < 5:
                return "Please provide more specific details."

            if task == TaskType.GENERAL and len(response.split()) > 40:
                return "Please provide more specific details."

            # -------- STORE --------
            self.cache.set(payload, response)

            return response

        except Exception:
            return "Please provide more specific details."

    # -------- STREAM (NO CACHE) --------
    def generate_stream(self, task: TaskType, query: str, context: str = ""):
        model = get_model_for_task(task)
        prompt = build_prompt(task=task, query=query, context=context)

        try:
            with self._lock:
                for token in self.client.generate_stream(model=model, prompt=prompt):
                    yield token

        except Exception:
            yield "Please provide more specific details."

    # -------- RAW (WITH CACHE) --------
    def generate_raw(self, prompt: str) -> str:
        model = get_model_for_task(TaskType.GENERAL)

        payload = {
            "task": "raw",
            "prompt": prompt,
            "model": model,
        }

        # -------- CACHE HIT --------
        cached = self.cache.get(payload)
        if cached:
            print("LLM CACHE HIT (RAW)")
            return cached

        try:
            with self._lock:
                response = self.client.generate(
                    model=model,
                    prompt=prompt,
                )

            if not response or len(response.strip()) < 5:
                raise ValueError("Empty response")

            # -------- STORE --------
            self.cache.set(payload, response)

            return response

        except Exception:
            raise
