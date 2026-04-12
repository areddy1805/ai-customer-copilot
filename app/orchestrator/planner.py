import json
import re
from app.orchestrator.plan_schema import Plan, Step
from app.llm.service import LLMService
from app.llm.models import TaskType


ALLOWED_TOOLS = {
    "get_order",
    "refund",
    "create_ticket",
    "fallback_rag",
}


class Planner:

    def __init__(self):
        self.llm = LLMService()

    # -----------------------------
    # DETERMINISTIC PLANNER (DAG-AWARE)
    # -----------------------------
    def create_plan(self, intent: str, query: str, context: str = "") -> Plan:

        order_ids = re.findall(r"ORD\d+", query.upper())
        steps = []
        step_id = 1

        if intent == "order_status":
            for oid in order_ids:
                steps.append(Step(step_id, "tool", "get_order", {"order_id": oid}, []))
                step_id += 1

        elif intent == "refund_request":
            for oid in order_ids:

                get_id = step_id
                steps.append(Step(get_id, "tool", "get_order", {"order_id": oid}, []))
                step_id += 1

                steps.append(
                    Step(step_id, "tool", "refund", {"order_id": oid}, [get_id])
                )
                step_id += 1

        elif intent in ["delivery_issue", "create_ticket"]:
            for oid in order_ids:

                get_id = step_id
                steps.append(Step(get_id, "tool", "get_order", {"order_id": oid}, []))
                step_id += 1

                steps.append(
                    Step(
                        step_id,
                        "tool",
                        "create_ticket",
                        {"order_id": oid, "issue": "delivery_issue"},
                        [get_id],
                    )
                )
                step_id += 1

        else:
            steps.append(Step(step_id, "tool", "fallback_rag", {"query": query}, []))

        steps = self._deduplicate_steps(steps)
        steps = self._reindex_steps(steps)

        return Plan(steps, query=query)

    # -----------------------------
    # LLM PLANNER (SANITIZE + FIX + DEDUP)
    # -----------------------------
    def _llm_plan(self, query: str, feedback: str = "", context: str = ""):

        prompt = f"""
Return a JSON DAG plan.

Rules:
- step_id (int), action="tool", tool_name, input, depends_on
- Only action: "tool"
- Max 3 steps
- No cycles

Query: {query}
"""

        try:
            response = self.llm.generate(TaskType.GENERAL, prompt)
            data = json.loads(response)

            raw_steps = []
            seen_ids = set()

            # -----------------------------
            # SANITIZE + NORMALIZE
            # -----------------------------
            for s in data.get("steps", []):

                step_id = s.get("step_id")
                tool_name = s.get("tool_name")
                action = s.get("action")
                depends_on = s.get("depends_on", [])

                if not isinstance(step_id, int) or step_id in seen_ids:
                    continue

                if tool_name not in ALLOWED_TOOLS:
                    continue

                # normalize action
                action = "tool"

                if not isinstance(depends_on, list):
                    continue

                raw_steps.append(
                    Step(
                        step_id,
                        action,
                        tool_name,
                        s.get("input", {}),
                        depends_on,
                    )
                )

                seen_ids.add(step_id)

            if not raw_steps:
                return None

            raw_steps = sorted(raw_steps, key=lambda x: x.step_id)

            # -----------------------------
            # ENFORCE DEPENDENCIES
            # -----------------------------
            corrected = []
            sid = 1

            for step in raw_steps:

                if step.tool_name == "refund":
                    oid = step.input.get("order_id")

                    get_step = Step(sid, "tool", "get_order", {"order_id": oid}, [])
                    refund_step = Step(
                        sid + 1, "tool", "refund", {"order_id": oid}, [sid]
                    )

                    corrected.extend([get_step, refund_step])
                    sid += 2

                else:
                    corrected.append(Step(sid, "tool", step.tool_name, step.input, []))
                    sid += 1

            # -----------------------------
            # DEDUP + REINDEX
            # -----------------------------
            corrected = self._deduplicate_steps(corrected)
            corrected = self._reindex_steps(corrected)

            return Plan(corrected[:3], query=query)

        except Exception:
            return None

    # -----------------------------
    # DEDUPLICATION
    # -----------------------------
    def _deduplicate_steps(self, steps):

        unique = {}
        remap = {}

        for step in steps:
            key = (step.tool_name, tuple(sorted(step.input.items())))

            if key not in unique:
                unique[key] = step
                remap[step.step_id] = step.step_id
            else:
                remap[step.step_id] = unique[key].step_id

        for step in unique.values():
            step.depends_on = list({remap.get(dep, dep) for dep in step.depends_on})

        return list(unique.values())

    # -----------------------------
    # REINDEX (CRITICAL)
    # -----------------------------
    def _reindex_steps(self, steps):

        id_map = {}
        new_steps = []

        for i, step in enumerate(sorted(steps, key=lambda x: x.step_id), start=1):
            id_map[step.step_id] = i

        for step in steps:
            new_steps.append(
                Step(
                    id_map[step.step_id],
                    step.action,
                    step.tool_name,
                    step.input,
                    [id_map[d] for d in step.depends_on if d in id_map],
                )
            )

        return sorted(new_steps, key=lambda x: x.step_id)
