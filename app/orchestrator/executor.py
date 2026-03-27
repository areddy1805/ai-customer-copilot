import time
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    data: dict = None
    error: str = None


class Executor:
    def __init__(self, tools: dict):
        self.tools = tools

    def execute(self, plan):

        results = []
        context = {}

        for step in plan.steps:

            tool = self.tools.get(step.action)

            if not tool:
                return ToolResult(success=False, error=f"Unknown tool {step.action}")

            inputs = {**context, **step.params}

            try:
                start = time.time()

                if callable(tool):
                    result = (
                        tool(**inputs) if isinstance(inputs, dict) else tool(inputs)
                    )
                else:
                    method = getattr(tool, self._resolve_method(step.action))
                    result = method(inputs)

                latency = int((time.time() - start) * 1000)

            except Exception as e:
                return ToolResult(success=False, error=str(e))

            if not result or not result.success:
                return result

            if result.data:
                step_data = result.data.copy()

                # attach observability metadata
                step_data["_tool"] = step.action
                step_data["_latency_ms"] = latency

                results.append(step_data)

                context.update(result.data)

        # -------- RETURN ALL STEP RESULTS --------
        return ToolResult(success=True, data={"steps": results})

    def _resolve_method(self, action):
        mapping = {
            "order": "get_order_status",
            "refund": "process_refund",
            "ticket": "create_ticket",
        }
        return mapping.get(action)
