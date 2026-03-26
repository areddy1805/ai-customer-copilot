import json
import re
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
    def create_plan(self, intent: str, query: str, context: str = "") -> Plan:

        order_ids = re.findall(r"ORD\d+", query.upper())

        steps = []

        if intent == "order_status":
            for oid in order_ids:
                steps.append(Step("order", {"order_id": oid}))

        elif intent == "refund_request":
            for oid in order_ids:
                steps.append(Step("order", {"order_id": oid}))
                steps.append(Step("refund", {"order_id": oid}))

        elif intent in ["delivery_issue", "create_ticket"]:
            for oid in order_ids:
                steps.append(Step("order", {"order_id": oid}))
                steps.append(
                    Step("ticket", {"order_id": oid, "issue": "delivery_issue"})
                )

        elif intent == "refund_policy":
            steps.append(Step("rag", {"query": query}))

        else:
            steps.append(Step("rag", {"query": query}))

        return Plan(steps, query=query)

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
