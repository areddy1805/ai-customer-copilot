from app.agent.schemas import Plan
from app.llm.service import LLMService
import json
import re


class AgentPlanner:

    def __init__(self):
        self.llm = LLMService()

    def create_plan(self, user_query: str, context: dict) -> Plan:
        prompt = self._build_prompt(user_query, context)

        raw = self.llm.generate_raw(prompt)
        print("RAW LLM OUTPUT:", raw)

        for _ in range(2):
            try:
                cleaned = self._extract_json(raw)
                print("CLEANED JSON:", cleaned)

                parsed = json.loads(cleaned)

                goal = parsed.get("goal", "").lower()

                # ===== NORMALIZATION LAYER =====
                for step in parsed.get("steps", []):

                    action = step.get("action")

                    # -------- FIX INVALID ACTION → TOOL --------
                    if action not in ["tool", "rag", "respond"]:
                        if action in ["get_order", "refund", "create_ticket"]:
                            step["tool_name"] = action
                            step["action"] = "tool"

                    # -------- FIX MISSING TOOL NAME --------
                    if step.get("action") == "tool" and not step.get("tool_name"):
                        raise ValueError("Missing tool_name in tool step")

                    # -------- ENSURE INPUT EXISTS --------
                    if step.get("action") == "tool" and "input" not in step:
                        step["input"] = {}

                    # -------- FORCE REFUND INPUT --------
                    if step.get("tool_name") == "refund":
                        if not step.get("input"):
                            match = re.search(r"ORD\d+", parsed.get("goal", "").upper())
                            if match:
                                step["input"] = {"order_id": match.group(0)}

                # ===== REMOVE INVALID REFUND (INTENT GUARD) =====
                cleaned_steps = []
                for step in parsed.get("steps", []):

                    if step.get("tool_name") == "refund" and "refund" not in goal:
                        continue

                    cleaned_steps.append(step)

                parsed["steps"] = cleaned_steps

                # ===== ENFORCE REFUND SEQUENCE =====
                tools = [
                    s.get("tool_name")
                    for s in parsed.get("steps", [])
                    if s.get("action") == "tool"
                ]

                if "refund" in tools:

                    has_order = "get_order" in tools

                    if not has_order:
                        order_match = re.search(
                            r"ORD\d+", parsed.get("goal", "").upper()
                        )
                        order_id = order_match.group(0) if order_match else "ORD1"

                        parsed["steps"].insert(
                            0,
                            {
                                "step_id": 0,
                                "action": "tool",
                                "tool_name": "get_order",
                                "input": {"order_id": order_id},
                            },
                        )

                # ===== ENSURE AT LEAST ONE TOOL =====
                if not any(s.get("action") == "tool" for s in parsed.get("steps", [])):
                    raise ValueError("No executable tool steps")

                # ===== ENSURE LAST STEP IS RESPOND =====
                if (
                    parsed.get("steps")
                    and parsed["steps"][-1].get("action") != "respond"
                ):
                    parsed["steps"].append(
                        {
                            "step_id": len(parsed["steps"]) + 1,
                            "action": "respond",
                        }
                    )

                normalized = json.dumps(parsed)

                return Plan.model_validate_json(normalized)

            except Exception:
                raw = self.llm.generate_raw(
                    prompt + "\n\nEnsure JSON is complete and valid."
                )

        raise ValueError("Failed to generate valid plan")

    def _extract_json(self, text: str) -> str:
        stack = []
        start = None

        for i, char in enumerate(text):
            if char == "{":
                if start is None:
                    start = i
                stack.append("{")

            elif char == "}":
                if stack:
                    stack.pop()
                    if not stack:
                        return text[start : i + 1]

        raise ValueError("No complete JSON object found")

    def _build_prompt(self, query, context):
        return f"""
You are a deterministic planning engine.

STRICT RULES:
- Output ONLY valid JSON
- No explanation text
- No markdown
- No code blocks
- Use ONLY provided tools
- DO NOT hallucinate tool names
- Extract order_id ONLY from current query
- NEVER reuse order_id from previous queries

CRITICAL TOOL RULE:
- ALWAYS use:
  action = "tool"
  tool_name = "<tool>"

INVALID:
- action = "refund"
- action = "get_order"

VALID:
- action = "tool", tool_name = "refund"

CRITICAL INTENT RULE:
- ONLY include refund step IF user explicitly asks for refund
- DO NOT add refund for:
  - tracking
  - order status
  - general queries

REFUND RULE (MANDATORY):
- If user asks for refund:
  Step 1 MUST be get_order
  Step 2 MUST be refund
  Step 3 MUST be respond
- refund ALWAYS requires input: {{ "order_id": "..." }}

FINAL STEP:
- MUST be "respond"

ACTION TYPES:
- tool
- rag
- respond

AVAILABLE TOOLS:
- get_order (input: order_id)
- refund (input: order_id)
- create_ticket (input: issue)

---

OUTPUT FORMAT:

{{
  "goal": "...",
  "steps": [
    {{
      "step_id": 1,
      "action": "tool",
      "tool_name": "get_order",
      "input": {{"order_id": "ORD1"}}
    }},
    {{
      "step_id": 2,
      "action": "respond"
    }}
  ]
}}

---

User query:
{query}

Return JSON:
"""
