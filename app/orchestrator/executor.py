import time
from dataclasses import dataclass
import asyncio

from app.orchestrator.tool_registry import ToolRegistry
from app.tools.order_tool import OrderTool
from app.tools.refund_tool import RefundTool
from app.tools.ticket_tool import TicketTool


@dataclass
class ToolResult:
    success: bool
    data: dict = None
    error: str = None


class Executor:

    def __init__(self, tool_registry=None):
        if tool_registry:
            self.tool_registry = tool_registry
        else:
            self.tool_registry = ToolRegistry()
            self.tool_registry.register("get_order", OrderTool())
            self.tool_registry.register("refund", RefundTool())
            self.tool_registry.register("create_ticket", TicketTool())

    def _get_tool_name(self, step):
        return getattr(step, "tool_name", None)

    def _get_step_input(self, step):
        if hasattr(step, "input") and step.input:
            return step.input
        return getattr(step, "params", {}) or {}

    def execute(self, plan):

        results = []
        context = {}

        for step in plan.steps:

            # SKIP NON-TOOL STEPS (CRITICAL FIX)
            if step.action != "tool":
                continue

            tool_name = self._get_tool_name(step)

            if not tool_name:
                continue

            try:
                tool = self.tool_registry.get(tool_name)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

            inputs = {**context, **self._get_step_input(step)}

            try:
                start = time.time()
                method = getattr(tool, self._resolve_method(tool_name))
                result = method(inputs)
                latency = int((time.time() - start) * 1000)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

            if not result or not result.success:

                results.append(
                    {
                        "_tool": tool_name,
                        "error": result.error if result else "Unknown error",
                        "_latency_ms": latency,
                    }
                )
                continue

            step_data = (result.data or {}).copy()
            step_data["_tool"] = tool_name
            step_data["_latency_ms"] = latency

            results.append(step_data)

            if result.data:
                context.update(result.data)

        return ToolResult(success=True, data={"steps": results})

    async def execute_parallel(self, plan):

        context = {}
        results = []

        for step in plan.steps:

            if step.action != "tool":
                continue

            tool_name = self._get_tool_name(step)

            if not tool_name:
                continue

            try:
                tool = self.tool_registry.get(tool_name)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

            inputs = {**context, **self._get_step_input(step)}

            try:
                start = time.time()
                method = getattr(tool, self._resolve_method(tool_name))
                result = method(inputs)
                latency = int((time.time() - start) * 1000)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

            if not result or not result.success:

                results.append(
                    {
                        "_tool": tool_name,
                        "error": result.error if result else "Unknown error",
                        "_latency_ms": latency,
                    }
                )
                continue

            step_data = (result.data or {}).copy()
            step_data["_tool"] = tool_name
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
                and all(dep in completed for dep in getattr(s, "depends_on", []))
            ]

            if not ready:
                return ToolResult(success=False, error="Deadlock in execution")

            tasks = [self._run_step(s, completed) for s in ready]

            outputs = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(ready, outputs):

                if step.action != "tool":
                    completed[step.step_id] = {}
                    continue

                tool_name = self._get_tool_name(step)

                if isinstance(result, Exception):
                    step_data = {
                        "_tool": tool_name,
                        "error": str(result),
                        "_latency_ms": 0,
                    }
                    completed[step.step_id] = step_data
                    results.append(step_data)
                    continue

                if not result or not result.success:
                    step_data = {
                        "_tool": tool_name,
                        "error": result.error if result else "Unknown error",
                        "_latency_ms": (
                            (result.data or {}).get("_latency_ms", 0)
                            if result and result.data
                            else 0
                        ),
                    }
                    completed[step.step_id] = step_data
                    results.append(step_data)
                    continue

                step_data = (result.data or {}).copy()
                step_data["_tool"] = tool_name
                step_data["_latency_ms"] = step_data.get("_latency_ms", 0)

                completed[step.step_id] = step_data
                results.append(step_data)

        return ToolResult(success=True, data={"steps": results})

    async def _run_step(self, step, completed):

        if step.action != "tool":
            return ToolResult(success=True, data={})

        tool_name = self._get_tool_name(step)

        try:
            tool = self.tool_registry.get(tool_name)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        context = {}

        for dep in getattr(step, "depends_on", []):
            context.update(completed.get(dep, {}))

        inputs = {**context, **self._get_step_input(step)}

        start = time.time()

        try:
            method = getattr(tool, self._resolve_method(tool_name))
            result = method(inputs)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        latency = int((time.time() - start) * 1000)

        if result and result.data:
            result.data["_latency_ms"] = latency
            result.data["_tool"] = tool_name

        return result

    def _resolve_method(self, action):
        mapping = {
            "get_order": "get_order_status",
            "refund": "process_refund",
            "create_ticket": "create_ticket",
        }

        method = mapping.get(action)

        if not method:
            raise ValueError(f"No method mapping for tool: {action}")

        return method
