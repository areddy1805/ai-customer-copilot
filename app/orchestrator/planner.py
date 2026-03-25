import json
from app.orchestrator.plan import Plan, Step
from app.llm.service import LLMService
from app.llm.models import TaskType


ALLOWED_ACTIONS = {
    "get_order",
    "check_refund_eligibility",
    "process_refund",
    "check_ticket",
    "create_or_fetch_ticket",
    "fallback_rag",
}


class Planner:

    def __init__(self):
        self.llm = LLMService()

    def create_plan(self, intent: str, query: str):

        q = query.lower()

        # -------- HARD RULES --------
        if "ticket" in q:
            return Plan(
                [
                    Step("get_order", {"query": query}),
                    Step("create_or_fetch_ticket", {}),
                ],
                query=query,
            )

        if intent == "refund_request":
            return Plan(
                [
                    Step("get_order", {"query": query}),
                    Step("check_refund_eligibility", {}),
                    Step("process_refund", {}),
                ],
                query=query,
            )

        if intent == "order_status":
            return Plan([Step("get_order", {"query": query})], query=query)

        if intent == "delivery_issue":
            return Plan(
                [
                    Step("get_order", {"query": query}),
                    Step("check_ticket", {}),
                    Step("create_or_fetch_ticket", {}),
                ],
                query=query,
            )

        # -------- LLM PLAN (ATTEMPT 1) --------
        plan = self._llm_plan(query)

        if plan:
            return plan

        # -------- RETRY WITH FEEDBACK --------
        plan = self._llm_plan(query, feedback="Previous plan invalid or empty")

        if plan:
            return plan

        # -------- FINAL FALLBACK --------
        return Plan([Step("fallback_rag", {"query": query})], query=query)

    # ================= LLM PLANNER =================
    def _llm_plan(self, query: str, feedback: str = "", context: str = ""):

        prompt = f"""
    Return a JSON plan.

    Conversation:
    {context}

    Allowed actions:
    {list(ALLOWED_ACTIONS)}

    Rules:
    - Max 3 steps
    - Only valid actions
    - No explanation

    Feedback:
    {feedback}

    Format:
    {{"steps": [{{"action": "...", "input": {{}}}}]}}

    Query: {query}
    """

        try:
            response = self.llm.generate(TaskType.GENERAL, prompt)
            data = json.loads(response)

            steps = []

            for s in data.get("steps", []):
                action = s.get("action")

                if action in ALLOWED_ACTIONS:
                    steps.append(Step(action, s.get("input", {})))

            if not steps:
                return None

            return Plan(steps[:3], query=query)

        except Exception:
            return None
