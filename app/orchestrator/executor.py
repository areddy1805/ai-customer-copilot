import time
from dataclasses import dataclass
import asyncio


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

                step_data = {
                    "_tool": step.action,
                    "error": result.error if result else "Unknown error",
                    "_latency_ms": latency,
                }

                results.append(step_data)
                continue

            if result.data:
                step_data = result.data.copy()
            else:
                step_data = {}

            step_data["_tool"] = step.action
            step_data["_latency_ms"] = latency

            results.append(step_data)

            if result.data:
                context.update(result.data)

        return ToolResult(success=True, data={"steps": results})

    def _resolve_method(self, action):
        mapping = {
            "order": "get_order_status",
            "refund": "process_refund",
            "ticket": "create_ticket",
        }
        return mapping.get(action)

    async def execute_parallel(self, plan):

        context = {}
        results = []

        for step in plan.steps:

            tool = self.tools.get(step.action)

            if not tool:
                return ToolResult(success=False, error=f"Unknown tool {step.action}")

            inputs = {**context, **step.params}

            try:
                start = time.time()

                if callable(tool):
                    result = tool(**inputs)
                else:
                    method = getattr(tool, self._resolve_method(step.action))
                    result = method(inputs)

                latency = int((time.time() - start) * 1000)

            except Exception as e:
                return ToolResult(success=False, error=str(e))

            if not result or not result.success:

                results.append(
                    {
                        "_tool": step.action,
                        "error": result.error if result else "Unknown error",
                        "_latency_ms": latency,
                    }
                )
                continue

            step_data = (result.data or {}).copy()
            step_data["_tool"] = step.action
            step_data["_latency_ms"] = latency

            results.append(step_data)

            if result.data:
                context.update(result.data)

        return ToolResult(success=True, data={"steps": results})

    async def execute_dag(self, plan):

        steps_map = {s.step_id: s for s in plan.steps}

        completed = {}
        results = []

        while len(completed) < len(steps_map):

            ready = [
                s
                for s in steps_map.values()
                if s.step_id not in completed
                and all(dep in completed for dep in s.depends_on)
            ]

            if not ready:
                return ToolResult(success=False, error="Deadlock in execution")

            tasks = [self._run_step(s, completed) for s in ready]

            outputs = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(ready, outputs):

                # -------- EXCEPTION CASE --------
                if isinstance(result, Exception):

                    step_data = {
                        "_tool": step.action,
                        "error": str(result),
                        "_latency_ms": 0,
                    }

                    completed[step.step_id] = step_data
                    results.append(step_data)
                    continue

                # -------- FAILURE CASE --------
                if not result or not result.success:

                    step_data = {
                        "_tool": step.action,
                        "error": result.error if result else "Unknown error",
                        "_latency_ms": (result.data or {}).get("_latency_ms", 0),
                    }

                    completed[step.step_id] = step_data
                    results.append(step_data)
                    continue

                # -------- SUCCESS CASE --------
                step_data = (result.data or {}).copy()

                if not step_data:
                    step_data = {}

                step_data["_tool"] = step.action
                step_data["_latency_ms"] = step_data.get("_latency_ms", 0)
                print("DAG STEP:", step.action, step_data)
                completed[step.step_id] = step_data
                results.append(step_data)

        return ToolResult(success=True, data={"steps": results})

    async def _run_step(self, step, completed):

        tool = self.tools.get(step.action)

        if not tool:
            return ToolResult(success=False, error=f"Unknown tool {step.action}")

        context = {}

        for dep in step.depends_on:
            context.update(completed.get(dep, {}))

        inputs = {**context, **step.params}

        start = time.time()

        try:
            if callable(tool):
                result = tool(**inputs)
            else:
                method = getattr(tool, self._resolve_method(step.action))
                result = method(inputs)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        latency = int((time.time() - start) * 1000)

        if result and result.data:
            result.data["_latency_ms"] = latency
            result.data["_tool"] = step.action

        return result
