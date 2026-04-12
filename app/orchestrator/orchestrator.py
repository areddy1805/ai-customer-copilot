import os
import uuid
import asyncio
import re
import time
from app.core.config import settings
from app.orchestrator.state import ConversationState
from app.orchestrator.classifier import IntentClassifier
from app.orchestrator.router import Router
from app.llm.service import LLMService
from app.llm.models import TaskType
from app.memory.memory_service import MemoryService
from app.rag.service import RAGService
from app.tools.order_tool import OrderTool
from app.tools.refund_tool import RefundTool
from app.tools.ticket_tool import TicketTool
from app.guard.policy_guard import PolicyGuard
from app.human.escalation_service import EscalationService
from app.core.logger import Logger
from app.cache.response_cache import ResponseCache
from app.security.rate_limiter import RateLimiter
from app.cache.inflight_registry import InFlightRegistry
from app.security.concurrency_limiter import ConcurrencyLimiter
from app.security.circuit_breaker import CircuitBreaker
from app.utils.retry import retry
from app.observability.metrics import Metrics
from app.guard.response_validator import ResponseValidator
from app.rag.embedder import Embedder
from app.cache.semantic_cache import SemanticCache
from app.orchestrator.planner import Planner
from app.orchestrator.plan import Plan, Step
from app.orchestrator.executor import Executor
from app.orchestrator.plan_validator import PlanValidator
from app.orchestrator.decomposer import Decomposer

from app.core.error_mapper import ErrorMapper

from app.agent.planner import AgentPlanner
from app.agent.validator import PlanValidator as AgentPlanValidator
from app.agent.schemas import Plan as AgentPlan


class Orchestrator:
    def __init__(self, executor):
        self.classifier = IntentClassifier()
        self.router = Router()
        self.llm = LLMService()
        self.memory = MemoryService()
        self.rag = RAGService()
        self.order_tool = OrderTool()
        self.refund_tool = RefundTool()
        self.ticket_tool = TicketTool()
        self.guard = PolicyGuard()
        self.escalation = EscalationService()
        self.logger = Logger()

        self.cache = ResponseCache()
        self.rate_limiter = RateLimiter()
        self.inflight = InFlightRegistry()
        self.concurrent = ConcurrencyLimiter(max_concurrent=5)

        self.llm_cb = CircuitBreaker()
        self.rag_cb = CircuitBreaker()

        self.llm_cb_stream = CircuitBreaker()
        self.rag_cb_stream = CircuitBreaker()

        self.metrics = Metrics()
        self.validator = ResponseValidator()

        self.embedder = Embedder()
        self.semantic_cache = SemanticCache(self.embedder)

        self.planner = Planner()
        self.executor = executor

        self.plan_validator = PlanValidator()
        self.decomposer = Decomposer()

        self.agent_planner = AgentPlanner()
        self.agent_validator = AgentPlanValidator()
        self.agent_enabled = settings.agent_enabled

        self.semantic_cache.store = []
        self.session_state = {}
        print("AGENT ENABLED:", self.agent_enabled)

    # ================= RUN =================

    def run(self, user_query: str, session_id: str) -> ConversationState:
        self.metrics.inc("requests_total")
        start_time = time.time()
        state = ConversationState(user_query=user_query)
        trace_id = str(uuid.uuid4())
        state.metadata["trace_id"] = trace_id

        def _to_str(resp):
            if isinstance(resp, str):
                return resp
            if hasattr(resp, "data"):
                data = getattr(resp, "data", None)
                if isinstance(data, dict) and "response" in data:
                    return data["response"]
                return str(data)
            return str(resp)

        def _exit(resp, status="success", error=None, clear_session=False):
            response = resp if isinstance(resp, str) else _to_str(resp)
            state.final_response = response

            latency = int((time.time() - start_time) * 1000)

            if status == "success":
                self.metrics.inc("requests_success")
            else:
                self.metrics.inc("requests_failure")

            if error == "user_requested_human":
                self.metrics.inc("requests_escalated")

            if error:
                mapped = ErrorMapper.map(error)
                self.metrics.inc(f"error_type_{mapped['error_type']}")
                self.metrics.inc(f"error_code_{mapped['error_code']}")

            self.metrics.observe("total_latency", latency)

            mapped_error = ErrorMapper.map(error) if error else None

            self.logger.log_request(
                session_id=session_id,
                user_query=user_query,
                intent=state.intent,
                route=state.metadata.get("route"),
                plans=state.metadata.get("plans"),
                tools_used=self._extract_tools(state.metadata.get("plans")),
                latency_ms=latency,
                status=status,
                error=mapped_error,
            )

            if clear_session:
                self.session_state.pop(session_id, None)

            return state

        try:
            # -------- RATE LIMIT --------
            if not self.rate_limiter.allow(session_id):
                return _exit(
                    "Too many requests. Please try again later.",
                    "failure",
                    "rate_limit",
                )

            # -------- GUARD --------
            guard = self.guard.evaluate(user_query, "unknown")
            if not guard["allowed"]:
                return _exit(
                    "Your request cannot be processed due to security or validation constraints.",
                    "failure",
                    "guard_block",
                )

            # -------- HUMAN --------
            if any(
                p in user_query.lower()
                for p in [
                    "talk to human",
                    "connect me to agent",
                    "customer support",
                    "human support",
                ]
            ):
                self._escalate(
                    session_id, user_query, "human_request", "User requested human"
                )
                return _exit(
                    "Connecting you to a support agent.",
                    "failure",
                    "user_requested_human",
                )

            # -------- SLOT RESOLUTION --------
            pending = self.session_state.get(session_id)
            if pending:
                order_id = self._extract_order_id(user_query)
                if order_id:
                    user_query = f"{pending['intent']} {order_id}"
                    intent = pending["intent"]
                else:
                    return _exit("Please provide a valid order ID.", "failure")
            else:
                intent = self.classifier.classify(user_query)

            q_lower = user_query.lower()

            if not pending:
                if "refund" in q_lower:
                    intent = "refund_request"
                elif "order" in q_lower or "track" in q_lower:
                    intent = "order_status"
                elif "ticket" in q_lower or "issue" in q_lower:
                    intent = "create_ticket"

            state.intent = intent
            self.metrics.inc(f"intent_{intent}")

            state.metadata["route"] = "rag" if intent == "refund_policy" else "tool"

            if intent == "general" and not pending:
                return _exit(
                    "I can help with order tracking, refunds, or delivery issues."
                )

            parts = [p.strip() for p in user_query.split(" and ") if p.strip()]

            rag_response = None
            tool_parts = []

            for part in parts:
                if "refund policy" in part.lower():
                    rag_response = _to_str(self.query(part))
                else:
                    tool_parts.append(part)

            order_id = self._extract_order_id(user_query)
            if (
                intent
                in ["order_status", "refund_request", "create_ticket", "delivery_issue"]
                and not order_id
            ):
                if not self.session_state.get(session_id):
                    self.session_state[session_id] = {"intent": intent}

                msg = {
                    "order_status": "Please provide your order ID to check order status.",
                    "refund_request": "Please provide your order ID to process refund request.",
                }.get(intent, "Please provide your order ID to create a ticket.")

                return _exit(msg)

            memory_context = self._get_memory_context(session_id)

            all_results = []
            state.metadata["plans"] = []

            def _run_task(task):

                if self.agent_enabled:
                    try:
                        agent_plan = self.agent_planner.create_plan(
                            user_query=task,
                            context={"memory": memory_context, "intent": intent},
                        )

                        self.agent_validator.validate(agent_plan)

                        state.metadata["plans"].append(
                            [
                                s.tool_name if s.action == "tool" else s.action
                                for s in agent_plan.steps
                            ]
                        )

                        # === FIX: USE NEW EXECUTOR ===
                        result = self.executor.execute(agent_plan)
                        return result

                    except Exception as e:
                        print("AGENT FAILURE:", str(e))

                plan = self._get_deterministic_plan(intent, task)
                state.metadata["plans"].append([step.action for step in plan.steps])

                # === FIX: REMOVE ASYNC EXECUTOR ===
                return self.executor.execute(plan)

            results = [_run_task(t) for t in (tool_parts or [user_query])]

            for res in results:

                if res is None:
                    continue

                if hasattr(res, "success") and hasattr(res, "data"):
                    res = res.data

                if isinstance(res, dict) and "steps" in res:
                    for step in res["steps"]:
                        if "_tool" in step:
                            self.metrics.observe(
                                f"tool_{step['_tool']}_latency",
                                step.get("_latency_ms", 0),
                            )
                        all_results.append(step)

                elif isinstance(res, dict):
                    all_results.append(res)

            print("ALL RESULTS:", all_results)

            responses = []

            for data in all_results:

                if not isinstance(data, dict):
                    continue

                tool = data.get("_tool")

                # === FIX: TOOL NAME ALIGNMENT ===
                if tool == "get_order":
                    responses.append(
                        f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."
                    )

                elif tool == "refund":
                    if data.get("error"):
                        responses.append(data.get("error"))
                    else:
                        responses.append(
                            f"Refund status for order {data.get('order_id')} is {data.get('status')}."
                        )

                elif tool == "create_ticket":
                    responses.append(
                        f"Ticket {data.get('ticket_id')} for order {data.get('order_id')} is currently {data.get('status')}."
                    )

                elif "response" in data:
                    responses.append(data["response"])

            response = (
                "Unable to process request. Please try again."
                if not responses
                else " ".join(responses)
            )

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", response)

            return _exit(response, clear_session=True)

        finally:
            pass

    # ================= STREAM =================
    def run_stream(self, user_query: str, session_id: str):

        state = self.run(user_query, session_id)
        response = state.final_response or ""

        for token in response.split(" "):
            yield token + " "
            time.sleep(0.02)

    # ================= HELPERS =================

    def _execute_agent_plan(self, agent_plan: AgentPlan):

        from app.orchestrator.plan import Plan, Step

        tool_map = {
            "get_order": "order",
            "refund": "refund",
            "create_ticket": "ticket",
        }

        steps = []

        # ===== BUILD DETERMINISTIC PLAN =====
        for s in agent_plan.steps:

            if s.action != "tool":
                continue

            mapped_tool = tool_map.get(s.tool_name)

            if not mapped_tool:
                raise ValueError(f"Invalid tool mapping: {s.tool_name}")

            params = s.input or {}

            # CRITICAL: enforce order_id for refund
            if mapped_tool == "refund" and "order_id" not in params:
                raise ValueError("Refund step missing order_id")

            steps.append(Step(mapped_tool, params))

        # ===== NO EXECUTABLE STEPS =====
        if not steps:
            return {"steps": [{"response": "No executable steps"}]}

        # ===== EXECUTE USING EXISTING ENGINE =====
        result = self.executor.execute(plan)

        final_steps = []

        if not result:
            return {"steps": [{"response": "Execution failed"}]}

        data = result.data or {}

        # ===== NORMAL SUCCESS PATH =====
        if result.success:

            if "steps" in data:
                final_steps.extend(data["steps"])
            else:
                final_steps.append(data)

        # ===== FAILURE PATH (PARTIAL SAFE) =====
        else:

            # convert failure into structured step
            final_steps.append(
                {
                    "_tool": steps[-1].action if steps else "unknown",
                    "error": result.error or "Execution failed",
                }
            )

        # ===== ENSURE STRUCTURE =====
        normalized = []

        for s in final_steps:
            if isinstance(s, dict):
                if "_tool" not in s:
                    continue
                normalized.append(s)

        return {"steps": normalized}

    def _build_agent_response(self, results):

        # ===== NO TRANSFORMATION =====
        # results already contain normalized tool outputs
        # preserve structure for orchestrator response builder

        steps = []

        for r in results.values():

            if not isinstance(r, dict):
                continue

            steps.append(r)

        return {"steps": steps}

    def _extract_tools(self, plans):
        tools = set()

        if not plans:
            return []

        for plan in plans:
            for step in plan:

                if not step:
                    continue

                # ===== AGENT PLAN (dict format) =====
                if isinstance(step, dict):
                    if step.get("action") != "tool":
                        continue

                    tool_name = step.get("tool")
                    if tool_name:
                        tools.add(tool_name)

                # ===== LEGACY PLAN (string format) =====
                elif isinstance(step, str):
                    if step in ["respond", "rag"]:
                        continue

                    # handles "order({...})" or similar repr
                    tool = step.split("(")[0]
                    tools.add(tool)

        return list(tools)

    def _extract_order_id(self, query: str):
        match = re.search(r"ORD0*(\d+)", query.upper())
        if match:
            return f"ORD{int(match.group(1))}"
        return None

    def _format_history(self, history):
        return "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in history)

    def _escalate(self, session_id, user_query, intent, reason):
        self.escalation.push(
            session_id=session_id,
            user_query=user_query,
            intent=intent,
            reason=reason,
        )

    def _normalize(self, query: str):
        return query.strip().lower()

    def _get_deterministic_plan(self, intent, user_query):

        if intent == "order_status":
            order_id = self._extract_order_id(user_query)

            if not order_id:
                return Plan(
                    [Step("ask_order_id", {"query": user_query})],
                    query=user_query,
                )

            return Plan(
                [Step("order", {"order_id": order_id})],
                query=user_query,
            )

        if intent == "refund_policy":
            return Plan(
                [Step("rag", {"query": user_query})],
                query=user_query,
            )

        if intent == "refund_request":
            order_id = self._extract_order_id(user_query)

            if not order_id:
                return Plan(
                    [Step("ask_order_id", {"query": user_query})],
                    query=user_query,
                )

            return Plan(
                [
                    Step("order", {"order_id": order_id}),
                    Step("refund", {"order_id": order_id}),  # FIXED
                ],
                query=user_query,
            )

        if intent in ["delivery_issue", "create_ticket"]:
            order_id = self._extract_order_id(user_query)

            if not order_id:
                return Plan(
                    [Step("ask_order_id", {"query": user_query})],
                    query=user_query,
                )

            return Plan(
                [
                    Step("order", {"order_id": order_id}),
                    Step("ticket", {}),
                ],
                query=user_query,
            )

        plan = self.planner.create_plan(intent, user_query)
        plan, _ = self.plan_validator.validate(plan)

        if not plan:
            return Plan(
                [Step("rag", {"query": user_query})],
                query=user_query,
            )

        return plan

    def _replan_on_failure(self, intent, user_query, reason, context=""):

        self.metrics.inc("execution_replan")

        feedback = f"Execution failed: {reason}"

        plan = self.planner._llm_plan(
            user_query,
            feedback=feedback,
            context=context,
        )

        plan, _ = self.plan_validator.validate(plan)

        if not plan:
            return Plan(
                [Step("fallback_rag", {"query": user_query})],
                query=user_query,
            )

        return plan

    def _get_memory_context(self, session_id, limit=5):

        history = self.memory.get_history(session_id)

        if not history:
            return ""

        recent = history[-limit:]

        return "\n".join(f"{m['role']}: {m['content']}" for m in recent)

    def _ask_order_id(self, query: str):
        from app.orchestrator.executor import ToolResult

        return ToolResult(
            success=True,
            data={"response": "Please provide your order ID to proceed."},
        )

    def query(self, query: str):
        from app.orchestrator.executor import ToolResult

        response = self.rag.generate(query)

        return ToolResult(
            success=True,
            data={"response": response},
        )

    def _get_valid_plan(self, intent, user_query, context=""):

        # -------- FORCE PLANNER FOR ALL CASES --------
        plan = self.planner.create_plan(intent, user_query, context)

        # -------- BASIC SAFETY CHECK --------
        if not plan or not getattr(plan, "steps", None):
            return Plan(
                [Step("rag", {"query": user_query})],
                query=user_query,
            )

        # -------- ENSURE EVERY STEP HAS PARAMS --------
        valid_steps = []

        for step in plan.steps:
            if not step.action:
                continue

            params = step.params or {}

            # enforce order_id if required
            if step.action in ["order", "refund", "ticket"]:
                if not params.get("order_id"):
                    order_id = self._extract_order_id(user_query)
                    if order_id:
                        params["order_id"] = order_id

            valid_steps.append(Step(step.action, params))

        if not valid_steps:
            return Plan(
                [Step("rag", {"query": user_query})],
                query=user_query,
            )

        return Plan(valid_steps, query=user_query)
