import json
from app.llm.service import LLMService
from app.llm.models import TaskType


class Decomposer:

    def __init__(self):
        self.llm = LLMService()

    def decompose(self, query: str, context: str = ""):

        prompt = f"""
    Break the query into atomic tasks.

    Conversation:
    {context}

    Rules:
    - Max 3 tasks
    - Each task must be independent
    - No explanation
    - Output JSON

    Format:
    {{"tasks": ["...", "..."]}}

    Query: {query}
    """

        try:
            response = self.llm.generate(TaskType.GENERAL, prompt)
            data = json.loads(response)

            tasks = data.get("tasks", [])

            if not tasks:
                return [query]

            return tasks[:3]

        except Exception:
            return [query]
