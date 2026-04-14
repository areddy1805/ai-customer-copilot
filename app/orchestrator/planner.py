import json
import re
from app.orchestrator.plan import Plan, Step
from app.orchestrator.constants import ALLOWED_ACTIONS


class Planner:
    def __init__(self, llm):
        self.llm = llm

    # ================= MAIN ENTRY =================
    async def create_plan(self, intent: str, query: str, context: str = "") -> Plan:
        feedback = ""

        for _ in range(2):
            plan = await self.llm_plan(query, feedback=feedback, context=context)

            if not plan:
                feedback = """
Your previous plan was invalid.

Issues:
- Invalid actions OR hallucinated values
- You introduced data not present in query

Fix:
- Use ONLY query data
- Use ONLY allowed actions
- Do NOT invent order_id
"""
                continue

            from app.orchestrator.plan_validator import PlanValidator

            validator = PlanValidator()
            validated_plan, error = validator.validate(plan)

            if validated_plan:
                return validated_plan

            feedback = f"Plan invalid: {error}"

        return self._fallback_plan(query)

    # ================= LLM PLANNER =================
    async def llm_plan(self, query: str, feedback: str = "", context: str = ""):
        prompt = f"""
You are an execution planner.

Convert query into steps.

STRICT RULES:
- Output ONLY JSON
- Max 3 steps
- Allowed actions ONLY: ["order", "refund", "ticket", "rag"]

CRITICAL:
- Use ONLY information present in query
- DO NOT invent order_id
- If no order_id → DO NOT use order/refund/ticket
- For informational queries → use "rag"

TASK IS ISOLATED:
- Do NOT use context or previous tasks

INVALID:
- refund policy → refund ORD123
- track ORD3 → track

VALID:
- refund policy → rag
- track ORD3 → order

FEEDBACK:
{feedback}

Examples:

Query: refund policy
{{"steps":[{{"action":"rag","input":{{"query":"refund policy"}}}}]}}

Query: track ORD123
{{"steps":[{{"action":"order","input":{{"order_id":"ORD123"}}}}]}}

Query:
{query}
"""

        try:
            response = await self.llm.generate(prompt, temperature=0, task="structured")

            print("PLANNER_RAW_RESPONSE:", response)

            match = re.search(r"\{[\s\S]*\}", response)
            if not match:
                return None

            data = json.loads(match.group(0))

            if not isinstance(data, dict) or "steps" not in data:
                return None

            steps = []

            for s in data["steps"]:
                action = s.get("action")
                params = s.get("input", {})

                # --- HARD VALIDATION ---
                if action not in ALLOWED_ACTIONS:
                    return None

                if action in ["order", "refund", "ticket"]:
                    if "order_id" not in params:
                        return None

                    # ensure order_id actually exists in query
                    if params["order_id"].upper() not in query.upper():
                        return None

                if action == "rag":
                    if not params.get("query"):
                        return None

                steps.append(Step(action, params))

            if not steps:
                return None

            # --- FORCE SINGLE PURPOSE PLAN ---
            if "policy" in query.lower():
                if any(s.action != "rag" for s in steps):
                    return None

            return Plan(steps[:3], query=query)

        except Exception as e:
            print("PLANNER_ERROR:", str(e))
            return None

    # ================= FALLBACK =================
    def _fallback_plan(self, query: str) -> Plan:
        order_ids = re.findall(r"ORD\d+", query.upper())

        if order_ids:
            return Plan([Step("order", {"order_id": order_ids[0]})], query=query)

        return Plan([Step("rag", {"query": query})], query=query)
