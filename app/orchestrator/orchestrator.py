import uuid
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


import re
import time


class Orchestrator:
    def __init__(self):
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
        self.executor = Executor(
            {
                "order": self.order_tool,
                "refund": self.refund_tool,
                "ticket": self.ticket_tool,
                "extract_order_id": self._extract_order_id,
                "ask_order_id": self._ask_order_id,
                "rag": self,
            }
        )

        self.plan_validator = PlanValidator()
        self.decomposer = Decomposer()

        self.semantic_cache.store = []

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

        def _exit(resp, status="success", error=None):
            response = resp if isinstance(resp, str) else _to_str(resp)
            state.final_response = response

            latency = int((time.time() - start_time) * 1000)

            # -------- METRICS --------
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

            # -------- LOG --------
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

            return state

        try:
            # -------- RATE LIMIT --------
            if not self.rate_limiter.allow(session_id):
                return _exit(
                    "Too many requests. Please try again later.",
                    status="failure",
                    error="rate_limit",
                )

            # -------- GUARD --------
            guard = self.guard.evaluate(user_query, "unknown")
            if not guard["allowed"]:
                return _exit(
                    "Your request cannot be processed due to security or validation constraints.",
                    status="failure",
                    error="guard_block",
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
                    status="failure",
                    error="user_requested_human",
                )

            # -------- CLASSIFY --------
            intent = self.classifier.classify(user_query)
            state.intent = intent
            self.metrics.inc(f"intent_{intent}")

            # -------- ROUTE --------
            state.metadata["route"] = "rag" if intent == "refund_policy" else "tool"

            key = f"{session_id}:{self._normalize(user_query)}"

            # -------- GENERAL --------
            if intent == "general":
                state.metadata["plans"] = []
                response = (
                    "I can help with order tracking, refunds, or delivery issues."
                )
                self.inflight.set(key, response)
                return _exit(response)

            # -------- DEDUP --------
            if not self.inflight.set_if_absent(key):
                return _exit(self.inflight.get(key))

            # -------- CACHE --------
            cached = self.semantic_cache.get(user_query)
            if cached:
                return _exit(_to_str(cached))

            cache_key = f"{intent}:{self._normalize(user_query)}"
            cached = self.cache.get(cache_key)
            if cached:
                return _exit(_to_str(cached))

            # -------- MEMORY --------
            memory_context = self._get_memory_context(session_id)

            # -------- RAG DIRECT --------
            if intent == "refund_policy":
                start = time.time()
                result = self.query(user_query)
                latency = int((time.time() - start) * 1000)

                self.metrics.observe("tool_rag_latency", latency)

                response = _to_str(result)
                state.metadata["plans"] = [["rag"]]

                self.inflight.set(key, response)
                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", response)

                return _exit(response)

            # -------- DECOMPOSE --------
            tasks = self.decomposer.decompose(user_query, memory_context)

            all_results = []
            state.metadata["plans"] = []

            for task in tasks:
                task_intent = self.classifier.classify(task)
                order_id = self._extract_order_id(task)

                # -------- SLOT HANDLING --------
                if task_intent == "order_status" and not order_id:
                    all_results.append(
                        type(
                            "Obj",
                            (),
                            {
                                "data": {
                                    "response": "Please provide your order ID to check order status."
                                }
                            },
                        )
                    )
                    continue

                if task_intent == "refund_request" and not order_id:
                    all_results.append(
                        type(
                            "Obj",
                            (),
                            {
                                "data": {
                                    "response": "Please provide your order ID to process refund request."
                                }
                            },
                        )
                    )
                    continue

                if task_intent in ["delivery_issue", "create_ticket"] and not order_id:
                    all_results.append(
                        type(
                            "Obj",
                            (),
                            {
                                "data": {
                                    "response": "Please provide your order ID to create a ticket."
                                }
                            },
                        )
                    )
                    continue

                # -------- PLAN --------
                plan = self.planner.create_plan(task_intent, task, memory_context)
                state.metadata["plans"].append([str(step) for step in plan.steps])

                # -------- EXECUTE --------
                result = self.executor.execute(plan)

                if not result or (hasattr(result, "success") and not result.success):
                    error = (
                        getattr(result, "error", "unknown_failure")
                        if result
                        else "no_result"
                    )

                    if error == "Order not found":
                        response = (
                            f"Order {order_id} not found. Please check your order ID."
                        )

                    elif "not delivered" in error.lower():
                        response = f"Refund status for order {order_id} is pending."

                    else:
                        self._escalate(session_id, user_query, task_intent, error)
                        return _exit(
                            "Your request has been escalated to a support agent.",
                            status="failure",
                            error=error,
                        )

                    all_results.append(
                        type("Obj", (), {"data": {"response": response}})
                    )
                    continue

                # -------- SAFE UNWRAP --------
                data = result.data or {}

                if "steps" in data:
                    for step_data in data["steps"]:
                        if "_tool" in step_data and "_latency_ms" in step_data:
                            self.metrics.observe(
                                f"tool_{step_data['_tool']}_latency",
                                step_data["_latency_ms"],
                            )

                        all_results.append(type("Obj", (), {"data": step_data}))
                else:
                    if "_tool" in data and "_latency_ms" in data:
                        self.metrics.observe(
                            f"tool_{data['_tool']}_latency",
                            data["_latency_ms"],
                        )

                    all_results.append(result)

            # -------- RESPONSE BUILD --------
            responses = []

            for res in all_results:
                data = getattr(res, "data", {})

                if "ticket_id" in data:
                    responses.append(
                        f"Ticket {data.get('ticket_id')} for order {data.get('order_id')} is currently {data.get('status')}."
                    )
                elif "delivery_eta" in data:
                    responses.append(
                        f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."
                    )
                elif "order_id" in data and "status" in data:
                    responses.append(
                        f"Refund status for order {data.get('order_id')} is {data.get('status')}."
                    )
                elif "response" in data:
                    responses.append(data["response"])
                else:
                    responses.append(str(data))

            response = " ".join(responses)

            self.inflight.set(key, response)
            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", response)

            return _exit(response)

        finally:
            pass

    # ================= STREAM =================
    def run_stream(self, user_query: str, session_id: str):

        def _to_str(resp):
            if isinstance(resp, str):
                return resp
            if hasattr(resp, "data"):
                data = getattr(resp, "data", None)
                if isinstance(data, dict) and "response" in data:
                    return data["response"]
                return str(data)
            return str(resp)

        self.metrics.inc("requests_total")
        start_time = time.time()
        state = ConversationState(user_query=user_query)

        key = f"{session_id}:{self._normalize(user_query)}"
        final_response = ""

        try:
            # -------- RATE LIMIT --------
            if not self.rate_limiter.allow(session_id):
                yield "Too many requests. Please try again later."
                return

            # -------- GUARD --------
            guard = self.guard.evaluate(user_query, "unknown")
            if not guard["allowed"]:
                yield "Your request cannot be processed due to security or validation constraints."
                return

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
                yield "Connecting you to a support agent."
                return

            # -------- CLASSIFY --------
            intent = self.classifier.classify(user_query)
            state.intent = intent
            self.metrics.inc(f"intent_{intent}")

            # -------- ROUTE --------
            if intent == "refund_policy":
                state.metadata["route"] = "rag"
            else:
                state.metadata["route"] = "tool"

            # -------- GENERAL --------
            if intent == "general":
                response = (
                    "I can help with order tracking, refunds, or delivery issues."
                )
                yield response
                return

            # -------- DEDUP --------
            if not self.inflight.set_if_absent(key):
                existing = self.inflight.get(key)
                if existing:
                    yield existing
                return

            # -------- CACHE --------
            cached = self.semantic_cache.get(user_query)
            if cached:
                yield cached
                return

            cache_key = f"{intent}:{self._normalize(user_query)}"
            cached = self.cache.get(cache_key)
            if cached:
                yield cached
                return

            # -------- MEMORY --------
            memory_context = self._get_memory_context(session_id)

            # -------- RAG --------
            if intent == "refund_policy":
                result = self.query(user_query)
                response = _to_str(result)

                state.metadata["plans"] = [["rag"]]

                for ch in response:
                    yield ch

                final_response = response

            else:
                # -------- DECOMPOSE --------
                tasks = self.decomposer.decompose(user_query, memory_context)

                all_results = []
                state.metadata["plans"] = []

                for task in tasks:

                    task_intent = self.classifier.classify(task)
                    order_id = self._extract_order_id(task)

                    # -------- SLOT --------
                    if task_intent == "order_status" and not order_id:
                        all_results.append(
                            {
                                "response": "Please provide your order ID to check order status."
                            }
                        )
                        continue

                    elif task_intent == "refund_request" and not order_id:
                        all_results.append(
                            {
                                "response": "Please provide your order ID to process refund request."
                            }
                        )
                        continue

                    elif (
                        task_intent in ["delivery_issue", "create_ticket"]
                        and not order_id
                    ):
                        all_results.append(
                            {
                                "response": "Please provide your order ID to create a ticket."
                            }
                        )
                        continue

                    # -------- PLAN --------
                    plan = self.planner.create_plan(task_intent, task, memory_context)
                    state.metadata["plans"].append([str(step) for step in plan.steps])

                    # -------- EXECUTE --------
                    result = self.executor.execute(plan)

                    if not result or (
                        hasattr(result, "success") and not result.success
                    ):

                        error = (
                            getattr(result, "error", "unknown_failure")
                            if result
                            else "no_result"
                        )

                        if error == "Order not found":
                            all_results.append(
                                {
                                    "response": f"Order {order_id} not found. Please check your order ID."
                                }
                            )
                        elif "not delivered" in error.lower():
                            all_results.append(
                                {
                                    "response": f"Refund status for order {order_id} is pending."
                                }
                            )
                        else:
                            self._escalate(session_id, user_query, task_intent, error)
                            yield "Your request has been escalated to a support agent."
                            return

                        continue

                    data = result.data or {}

                    if "steps" in data:
                        all_results.extend(data["steps"])
                    else:
                        all_results.append(data)

                # -------- BUILD RESPONSE --------
                responses = []

                for data in all_results:

                    if "ticket_id" in data:
                        responses.append(
                            f"Ticket {data.get('ticket_id')} for order {data.get('order_id')} is currently {data.get('status')}."
                        )

                    elif "delivery_eta" in data:
                        responses.append(
                            f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."
                        )

                    elif "order_id" in data and "status" in data:
                        responses.append(
                            f"Refund status for order {data.get('order_id')} is {data.get('status')}."
                        )

                    elif "response" in data:
                        responses.append(data["response"])

                    else:
                        responses.append(str(data))

                final_response = " ".join(responses)

                for ch in final_response:
                    yield ch

            # -------- STORE --------
            self.inflight.set(key, final_response)
            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", final_response)

            latency = int((time.time() - start_time) * 1000)

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

            self.metrics.observe("total_latency", latency)

        except Exception as e:

            latency = int((time.time() - start_time) * 1000)

            self.logger.log_request(
                session_id=session_id,
                user_query=user_query,
                intent="unknown",
                route="unknown",
                plans=[],
                tools_used=[],
                latency_ms=latency,
                status="failure",
                error=str(e),
            )

            yield "Something went wrong. Your request has been escalated."

    # ================= HELPERS =================
    def _extract_tools(self, plans):
        tools = set()

        if not plans:
            return []

        for plan in plans:
            for step in plan:
                if "(" in step:
                    tool = step.split("(")[0]
                    tools.add(tool)

        return list(tools)

    def _extract_order_id(self, query: str):
        match = re.search(r"ORD\d+", query.upper())
        return match.group(0) if match else None

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
                    Step("refund", {}),
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
