import time
import asyncio
from dataclasses import dataclass
from collections import defaultdict, deque

from app.orchestrator.tool_registry import ToolRegistry
from app.tools.order_tool import OrderTool
from app.tools.refund_tool import RefundTool
from app.tools.ticket_tool import TicketTool
from app.core.cache import SimpleCache
from app.core.errors import ErrorCode


# -----------------------------
# RESULT MODEL
# -----------------------------
@dataclass
class ToolResult:
    success: bool
    data: dict = None
    error: str = None


# -----------------------------
# DAG UTILITIES
# -----------------------------
def build_execution_graph(steps):
    graph = defaultdict(list)
    in_degree = {step.step_id: 0 for step in steps}
    step_map = {step.step_id: step for step in steps}

    for step in steps:
        for dep in getattr(step, "depends_on", []):
            graph[dep].append(step.step_id)
            in_degree[step.step_id] += 1

    return graph, in_degree, step_map


def get_execution_order(graph, in_degree):
    queue = deque(sorted([n for n in in_degree if in_degree[n] == 0]))
    order = []

    while queue:
        current = queue.popleft()
        order.append(current)

        for neighbor in sorted(graph[current]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(in_degree):
        raise ValueError("Cycle detected in plan")

    return order


# -----------------------------
# EXECUTOR
# -----------------------------
class Executor:

    def __init__(self, tool_registry=None):
        self.cache = SimpleCache(ttl=30)

        if tool_registry:
            self.tool_registry = tool_registry
        else:
            self.tool_registry = ToolRegistry()
            self.tool_registry.register("get_order", OrderTool())
            self.tool_registry.register("refund", RefundTool())
            self.tool_registry.register("create_ticket", TicketTool())

    # -----------------------------
    # HELPERS
    # -----------------------------
    def _get_tool_name(self, step):
        return getattr(step, "tool_name", None)

    def _get_step_input(self, step):
        if hasattr(step, "input") and step.input:
            return step.input
        return getattr(step, "params", {}) or {}

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

    # -----------------------------
    # SEQUENTIAL DAG EXECUTION
    # -----------------------------
    def execute(self, plan):

        graph, in_degree, step_map = build_execution_graph(plan.steps)
        order = get_execution_order(graph, in_degree)

        results = []
        completed = {}
        failed_steps = set()
        trace_id = getattr(plan, "trace_id", None)

        for step_id in order:
            step = step_map[step_id]

            if step.action != "tool":
                completed[step_id] = {}
                continue

            tool_name = self._get_tool_name(step)

            if not tool_name:
                completed[step_id] = {}
                continue

            # -------- DEPENDENCY FAIL --------
            if any(dep in failed_steps for dep in getattr(step, "depends_on", [])):
                step_data = {
                    "_tool": tool_name,
                    "_step_id": step_id,
                    "_depends_on": getattr(step, "depends_on", []),
                    "_trace_id": trace_id,
                    "_status": "skipped",
                    "_latency_ms": 0,
                    "error": "Dependency failed",
                    "error_code": ErrorCode.DEPENDENCY_FAILED,
                    **self._get_step_input(step),
                }
                completed[step_id] = step_data
                failed_steps.add(step_id)
                results.append(step_data)
                continue

            try:
                tool = self.tool_registry.get(tool_name)
            except Exception as e:
                return ToolResult(
                    success=False,
                    error=str(e),
                    data={
                        **self._get_step_input(step),
                        "error_code": ErrorCode.UNKNOWN_ERROR,
                    },
                )

            context = self._build_dependency_context(step, completed)
            inputs = {**context, **self._get_step_input(step)}

            # -------- CACHE --------
            cached = self.cache.get(tool_name, inputs)

            if cached:
                result = cached
                latency = 0
            else:
                max_retries = 2
                attempt = 0

                while attempt <= max_retries:
                    try:
                        start = time.time()
                        method = getattr(tool, self._resolve_method(tool_name))
                        result = method(inputs)
                        latency = int((time.time() - start) * 1000)
                        break
                    except Exception as e:
                        attempt += 1
                        if attempt > max_retries:
                            failed_steps.add(step_id)
                            return ToolResult(
                                success=False,
                                error=str(e),
                                data={
                                    **self._get_step_input(step),
                                    "error_code": ErrorCode.UNKNOWN_ERROR,
                                },
                            )

                if result and result.success:
                    self.cache.set(tool_name, inputs, result)

            # -------- FAILURE --------
            if not result or not result.success:
                step_data = {
                    "_tool": tool_name,
                    "_step_id": step_id,
                    "_depends_on": getattr(step, "depends_on", []),
                    "_trace_id": trace_id,
                    "_status": "failed",
                    "_latency_ms": latency,
                    "error": result.error if result else "Unknown error",
                    "error_code": (
                        getattr(result, "error_code", None)
                        or (result.data or {}).get("error_code")
                        or ErrorCode.UNKNOWN_ERROR
                    ),
                    **self._get_step_input(step),
                }

                completed[step_id] = step_data
                failed_steps.add(step_id)
                results.append(step_data)
                continue

            # -------- SUCCESS --------
            step_data = (result.data or {}).copy()
            step_data.update(
                {
                    "_tool": tool_name,
                    "_step_id": step_id,
                    "_depends_on": getattr(step, "depends_on", []),
                    "_trace_id": trace_id,
                    "_status": "success",
                    "_latency_ms": latency,
                }
            )

            completed[step_id] = step_data
            results.append(step_data)

        return ToolResult(success=True, data={"steps": results})

    # -----------------------------
    # PARALLEL DAG EXECUTION
    # -----------------------------
    async def execute_dag(self, plan):

        steps_map = {s.step_id: s for s in plan.steps}
        completed = {}
        results = []
        failed_steps = set()
        trace_id = getattr(plan, "trace_id", None)

        while len(completed) < len(steps_map):

            ready = sorted(
                [
                    s
                    for s in steps_map.values()
                    if s.step_id not in completed
                    and all(dep in completed for dep in getattr(s, "depends_on", []))
                ],
                key=lambda x: x.step_id,
            )

            if not ready:
                return ToolResult(success=False, error="Deadlock in execution")

            tasks = [
                self._run_step(s, completed, trace_id, failed_steps) for s in ready
            ]
            outputs = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(ready, outputs):

                if step.action != "tool":
                    completed[step.step_id] = {}
                    continue

                tool_name = self._get_tool_name(step)

                if isinstance(result, Exception):
                    failed_steps.add(step.step_id)
                    step_data = {
                        "_tool": tool_name,
                        "_step_id": step.step_id,
                        "_depends_on": getattr(step, "depends_on", []),
                        "_trace_id": trace_id,
                        "_status": "failed",
                        "_latency_ms": 0,
                        "error": str(result),
                        "error_code": ErrorCode.UNKNOWN_ERROR,
                        **self._get_step_input(step),
                    }
                    completed[step.step_id] = step_data
                    results.append(step_data)
                    continue

                if not result or not result.success:
                    failed_steps.add(step.step_id)
                    step_data = {
                        "_tool": tool_name,
                        "_step_id": step.step_id,
                        "_depends_on": getattr(step, "depends_on", []),
                        "_trace_id": trace_id,
                        "_status": "failed",
                        "_latency_ms": (
                            (result.data or {}).get("_latency_ms", 0)
                            if result and result.data
                            else 0
                        ),
                        "error": result.error if result else "Unknown error",
                        "error_code": (
                            getattr(result, "error_code", None)
                            or (result.data or {}).get("error_code")
                            or ErrorCode.UNKNOWN_ERROR
                        ),
                        **self._get_step_input(step),
                    }
                    completed[step.step_id] = step_data
                    results.append(step_data)
                    continue

                step_data = (result.data or {}).copy()
                step_data.update(
                    {
                        "_tool": tool_name,
                        "_step_id": step.step_id,
                        "_depends_on": getattr(step, "depends_on", []),
                        "_trace_id": trace_id,
                        "_status": "success",
                        "_latency_ms": step_data.get("_latency_ms", 0),
                    }
                )

                completed[step.step_id] = step_data
                results.append(step_data)

        return ToolResult(success=True, data={"steps": results})

    # -----------------------------
    # STEP RUNNER
    # -----------------------------
    async def _run_step(self, step, completed, trace_id, failed_steps):

        if step.action != "tool":
            return ToolResult(success=True, data={})

        tool_name = self._get_tool_name(step)

        if any(dep in failed_steps for dep in getattr(step, "depends_on", [])):
            return ToolResult(
                success=False,
                error="Dependency failed",
                data={
                    **self._get_step_input(step),
                    "error_code": ErrorCode.DEPENDENCY_FAILED,
                },
            )

        try:
            tool = self.tool_registry.get(tool_name)
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                data={
                    **self._get_step_input(step),
                    "error_code": ErrorCode.UNKNOWN_ERROR,
                },
            )

        context = self._build_dependency_context(step, completed)
        inputs = {**context, **self._get_step_input(step)}

        cached = self.cache.get(tool_name, inputs)

        if cached:
            result = cached
            if result and result.data:
                result.data["_latency_ms"] = 0
            return result

        max_retries = 2
        attempt = 0

        while attempt <= max_retries:
            try:
                start = time.time()
                method = getattr(tool, self._resolve_method(tool_name))
                result = method(inputs)
                latency = int((time.time() - start) * 1000)
                break
            except Exception as e:
                attempt += 1
                if attempt > max_retries:
                    return ToolResult(
                        success=False,
                        error=str(e),
                        data={
                            **self._get_step_input(step),
                            "error_code": ErrorCode.UNKNOWN_ERROR,
                        },
                    )

        if result and result.success:
            self.cache.set(tool_name, inputs, result)

        if result and result.data:
            result.data["_latency_ms"] = latency

        return result

    # -----------------------------
    # CONTEXT BUILDER
    # -----------------------------
    def _build_dependency_context(self, step, completed):
        context = {}

        for dep in getattr(step, "depends_on", []):
            if dep not in completed:
                raise ValueError(f"Missing dependency result for step {dep}")

            dep_data = completed[dep]
            clean_data = {k: v for k, v in dep_data.items() if not k.startswith("_")}
            context.update(clean_data)

        return context
