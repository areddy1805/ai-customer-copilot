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

# from app.orchestrator.tool_registry import ToolRegistry
# from app.orchestrator.tool_selector import ToolSelector


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

        # self.tool_registry = ToolRegistry(self.embedder)

        # self.tool_registry.register(
        #     "order_status", "Check order status, tracking, delivery date"
        # )

        # self.tool_registry.register(
        #     "refund_request", "Process refund, money back, return product"
        # )

        # self.tool_registry.register(
        #     "create_ticket", "Create support ticket, report issue, complaint"
        # )

        # self.tool_selector = ToolSelector(self.tool_registry)

        self.semantic_cache.store = []

    # ================= RUN =================
    def run(self, user_query: str, session_id: str) -> ConversationState:

        def _to_str(resp):
            if isinstance(resp, str):
                return resp
            if hasattr(resp, "data"):
                data = getattr(resp, "data", None)
                if isinstance(data, dict) and "response" in data:
                    return data["response"]
                return str(data)
            return str(resp)

        def _exit(resp):
            state.final_response = resp if isinstance(resp, str) else _to_str(resp)
            return state

        self.metrics.inc("requests_total")
        start_time = time.time()
        state = ConversationState(user_query=user_query)

        try:
            # -------- RATE LIMIT --------
            if not self.rate_limiter.allow(session_id):
                return _exit("Too many requests. Please try again later.")

            # -------- GUARD --------
            guard = self.guard.evaluate(user_query, "unknown")
            if not guard["allowed"]:
                return _exit(
                    "Your request cannot be processed due to security or validation constraints."
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
                return _exit("Connecting you to a support agent.")

            # -------- CLASSIFY --------
            intent = self.classifier.classify(user_query)
            state.intent = intent

            # -------- ROUTE --------
            if intent == "refund_policy":
                state.metadata["route"] = "rag"
            else:
                state.metadata["route"] = "tool"

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
                existing = self.inflight.get(key)
                return _exit(existing)

            # -------- CACHE --------
            cached = self.semantic_cache.get(user_query)
            if cached:
                cached = _to_str(cached)
                self.inflight.set(key, cached)
                return _exit(cached)

            cache_key = f"{intent}:{self._normalize(user_query)}"
            cached = self.cache.get(cache_key)
            if cached:
                cached = _to_str(cached)
                self.inflight.set(key, cached)
                return _exit(cached)

            # -------- MEMORY --------
            memory_context = self._get_memory_context(session_id)

            # -------- RAG DIRECT --------
            if intent == "refund_policy":
                result = self.query(user_query)
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

                elif task_intent == "refund_request" and not order_id:
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

                elif (
                    task_intent in ["delivery_issue", "create_ticket"] and not order_id
                ):
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
                            "Your request has been escalated to a support agent."
                        )

                    all_results.append(
                        type("Obj", (), {"data": {"response": response}})
                    )
                    continue

                # -------- UNWRAP EXECUTOR --------
                data = result.data or {}

                if "steps" in data:
                    for step_data in data["steps"]:
                        all_results.append(type("Obj", (), {"data": step_data}))
                else:
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

            # -------- STORE --------
            self.inflight.set(key, response)
            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", response)

            latency = int((time.time() - start_time) * 1000)
            self.metrics.observe("total_latency", latency)

            return _exit(response)

        finally:
            pass

    # ================= STREAM =================
    def run_stream(self, user_query: str, session_id: str):
        key = None
        final_response = ""

        try:
            # -------- RATE LIMIT --------
            if not self.rate_limiter.allow(session_id):
                yield "Too many requests. Please try again later."
                return

            # -------- GUARD (VALIDATION ONLY) --------
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

            # -------- INTENT --------
            intent = self.classifier.classify(user_query)

            key = f"{session_id}:{self._normalize(user_query)}"

            # -------- DEDUP --------
            if not self.inflight.set_if_absent(key):
                self.metrics.inc("dedup_hits")
                existing = self.inflight.get(key)
                if existing:
                    yield existing
                return

            # -------- CACHE --------
            cached = self.semantic_cache.get(user_query)
            if cached:
                self.metrics.inc("semantic_cache_hits")
                self.inflight.set(key, cached)
                yield cached
                return
            else:
                self.metrics.inc("semantic_cache_misses")

            cache_key = f"{intent}:{self._normalize(user_query)}"
            cached = self.cache.get(cache_key)
            if cached:
                self.metrics.inc("cache_hits")
                self.inflight.set(key, cached)
                yield cached
                return
            else:
                self.metrics.inc("cache_misses")

            # -------- MEMORY --------
            memory_context = self._get_memory_context(session_id)

            # ================================
            # 🔴 FIX: PLANNER IS MANDATORY
            # ================================
            plan = self._get_valid_plan(intent, user_query, memory_context)

            # -------- EXECUTE PLAN --------
            result = self.executor.execute(plan)

            # -------- FAILURE HANDLING --------
            if not result or (hasattr(result, "success") and not result.success):

                if intent == "refund_request":
                    final_response = "Refund cannot be processed because the order is not delivered yet."
                elif intent == "order_status":
                    final_response = "Order not found. Please check your order ID."
                else:
                    self._escalate(session_id, user_query, intent, "execution_failed")
                    final_response = (
                        "Your request has been escalated to a support agent."
                    )

                self.inflight.set(key, final_response)

                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", final_response)

                yield final_response
                return

            # -------- RESPONSE BUILD (MANDATORY) --------
            data = getattr(result, "data", None)

            if not data:
                final_response = "Unable to process request."
                self.inflight.set(key, final_response)
                yield final_response
                return

            if intent == "order_status":
                final_response = f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."
            elif intent == "refund_request":
                final_response = f"Refund status for order {data.get('order_id')} is {data.get('status')}."
            elif intent in ["create_ticket", "delivery_issue"]:
                final_response = (
                    f"Ticket {data.get('ticket_id')} is currently {data.get('status')}."
                )
            elif intent == "refund_policy":
                final_response = str(data)
            else:
                final_response = str(data)

            # -------- STREAM OUTPUT --------
            for ch in final_response:
                yield ch

            # -------- STORE --------
            self.inflight.set(key, final_response)
            self.metrics.inc("requests_success")

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", final_response)

            if (
                final_response
                and len(final_response) > 20
                and "escalated" not in final_response.lower()
            ):
                self.semantic_cache.set(user_query, final_response)

            return

        except Exception:
            if key:
                self.inflight.delete(key)

            yield "Something went wrong. Your request has been escalated."

    # ================= HELPERS =================

    def _log(self, session_id, query, intent, route, execution, start_time, metadata):
        try:
            latency = int((time.time() - start_time) * 1000)
            status = (
                "failure" if execution in ["escalated", "system_failure"] else "success"
            )

            self.logger.log_request(
                session_id=session_id,
                user_query=query,
                intent=intent,
                route=route,
                execution=execution,
                latency_ms=latency,
                status=status,
                extra=metadata or {},
            )
        except:
            pass

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
