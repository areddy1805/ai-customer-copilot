from app.orchestrator.plan import Plan, Step
from app.orchestrator.constants import ALLOWED_ACTIONS
import re


class PlanValidator:

    def _has_order_id(self, query: str):
        if not query:
            return False
        return bool(re.search(r"\d{3,}", query))

    def validate(self, plan: Plan):

        # ---- EMPTY PLAN ----
        if not plan or not plan.steps:
            return (
                Plan(
                    steps=[Step(action="fallback", params={"reason": "empty_plan"})],
                    query=getattr(plan, "query", ""),
                ),
                None,
            )

        valid_steps = []

        for step in plan.steps:

            # ---- ALLOWED ACTION FILTER ----
            if step.action not in ALLOWED_ACTIONS:
                continue

            # ---- RAG VALIDATION ----
            if step.action == "rag":
                query = ""

                if isinstance(step.params, dict):
                    query = step.params.get("query", "")

                if not query:
                    query = getattr(plan, "query", "")

                # block rag only if query clearly contains order id
                if self._has_order_id(query):
                    return None, "invalid_rag_for_order"

            valid_steps.append(step)

        # ---- NO VALID STEPS → FALLBACK ----
        if not valid_steps:
            return (
                Plan(
                    steps=[
                        Step(action="fallback", params={"reason": "no_valid_steps"})
                    ],
                    query=plan.query,
                ),
                None,
            )

        # ---- TOO MANY STEPS ----
        if len(valid_steps) > 3:
            return (
                Plan(
                    steps=[
                        Step(action="fallback", params={"reason": "too_many_steps"})
                    ],
                    query=plan.query,
                ),
                None,
            )

        return Plan(valid_steps, query=plan.query), None
