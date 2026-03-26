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
from app.orchestrator.tool_registry import ToolRegistry
from app.orchestrator.tool_selector import ToolSelector


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
            }
        )

        self.plan_validator = PlanValidator()
        self.decomposer = Decomposer()

        self.tool_registry = ToolRegistry(self.embedder)

        self.tool_registry.register(
            "order_status", "Check order status, tracking, delivery date"
        )

        self.tool_registry.register(
            "refund_request", "Process refund, money back, return product"
        )

        self.tool_registry.register(
            "create_ticket", "Create support ticket, report issue, complaint"
        )

        self.tool_selector = ToolSelector(self.tool_registry)

        self.semantic_cache.store = []

    # ================= RUN =================
    def run(self, user_query: str, session_id: str) -> ConversationState:
        self.metrics.inc("requests_total")
        start_time = time.time()
        state = ConversationState(user_query=user_query)

        intent = None
        route = None
        key = None
        acquired = False

        try:
            # -------- RATE LIMIT --------
            if not self.rate_limiter.allow(session_id):
                self.metrics.inc("rate_limited")
                state.final_response = "Too many requests. Please try again later."
                state.metadata["execution"] = "rate_limited"
                self._log(
                    session_id,
                    user_query,
                    intent,
                    route,
                    "rate_limited",
                    start_time,
                    state.metadata,
                )
                return state

            # -------- GUARD --------
            guard = self.guard.evaluate(user_query, "unknown")
            if not guard["allowed"]:
                state.final_response = "Your request cannot be processed due to security or validation constraints."
                state.metadata["execution"] = "blocked"
                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", state.final_response)
                self._log(
                    session_id,
                    user_query,
                    intent,
                    route,
                    "blocked",
                    start_time,
                    state.metadata,
                )
                return state

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
                state.final_response = "Connecting you to a support agent."
                state.metadata["execution"] = "human_escalation"
                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", state.final_response)
                self._log(
                    session_id,
                    user_query,
                    "human_request",
                    None,
                    "human_escalation",
                    start_time,
                    state.metadata,
                )
                return state

            # -------- CLASSIFY --------
            intent = self.classifier.classify(user_query)

            state.intent = intent

            key = f"{session_id}:{self._normalize(user_query)}"

            # -------- DEDUP --------
            if not self.inflight.set_if_absent(key):
                existing = self.inflight.get(key)
                if existing:
                    state.final_response = existing
                return state

            # -------- ROUTE --------
            if intent in [
                "order_status",
                "refund_request",
                "delivery_issue",
                "create_ticket",
            ]:
                route = "tool"
            else:
                tool_match = self.tool_selector.select(user_query)

                if tool_match:
                    route = "tool"
                    intent = tool_match
                else:
                    route = self.router.route(intent)

            cache_key = f"{intent}:{self._normalize(user_query)}"

            # -------- CACHE --------
            # -------- SEMANTIC CACHE --------
            cached = self.semantic_cache.get(user_query)

            if cached:
                self.metrics.inc("semantic_cache_hits")
                self.inflight.set(key, cached)
                state.final_response = cached
                return state
            else:
                self.metrics.inc("semantic_cache_misses")

            # -------- EXACT CACHE --------
            cached = self.cache.get(cache_key)

            if cached:
                self.metrics.inc("cache_hits")
                self.inflight.set(key, cached)
                state.final_response = cached
                return state
            else:
                self.metrics.inc("cache_misses")

            # -------- GUARD 2 --------
            guard = self.guard.evaluate(user_query, intent)

            # -------- TOOL --------
            memory_context = self._get_memory_context(session_id)

            tasks = [user_query]

            final_result = None

            last_intent = intent

            plan = None

            for task in tasks:

                # DO NOT reclassify core intents
                if intent in [
                    "order_status",
                    "refund_request",
                    "delivery_issue",
                    "create_ticket",
                ]:
                    sub_intent = intent
                else:
                    sub_intent = self.classifier.classify(task)

                last_intent = sub_intent

                plan = self._get_valid_plan(last_intent, task, memory_context)

                if "plans" not in state.metadata:
                    state.metadata["plans"] = []

                state.metadata["plans"].append([step.action for step in plan.steps])

                # route override AFTER plan exists
                if plan.steps and plan.steps[0].action == "fallback_rag":
                    state.metadata["route"] = "rag"
                else:
                    state.metadata["route"] = route

                if plan.steps and plan.steps[0].action == "fallback_rag":
                    response = self.rag.generate(user_query)

                    state.final_response = response
                    self.inflight.set(key, response)

                    self.memory.add_message(session_id, "user", user_query)
                    self.memory.add_message(session_id, "assistant", response)

                    self.metrics.inc("requests_success")
                    return state

                result = self.executor.execute(plan)

                if not result:
                    continue

                # -------- EARLY SUCCESS EXIT (CRITICAL FIX--------
                if hasattr(result, "data") and last_intent == "order_status":
                    data = getattr(result, "data", None)

                    if data is None:
                        continue

                    final_result = result
                    break

                # -------- FAILURE → REPLAN --------
                if hasattr(result, "success") and not result.success:

                    # -------- REFUND SPECIAL CASE (NO ESCALATION--------
                    if last_intent == "refund_request":
                        state.final_response = "Refund cannot be processed because the order is not delivered yet."
                        self.inflight.set(key, state.final_response)

                        self.memory.add_message(session_id, "user", user_query)
                        self.memory.add_message(
                            session_id, "assistant", state.final_response
                        )

                        self.metrics.inc("requests_success")
                        return state

                    # -------- OTHER FAILURES --------
                    reason = getattr(result, "error", "unknown_failure")

                    recovery_plan = self._replan_on_failure(
                        last_intent, task, reason, memory_context
                    )

                    if recovery_plan.steps != plan.steps:
                        result = self.executor.execute(recovery_plan)

                        if result and (
                            not hasattr(result, "success") or result.success
                        ):
                            state.metadata["execution_recovered"] = True
                        else:
                            self.metrics.inc("execution_replan_failed")
                    else:
                        self.metrics.inc("execution_replan_skipped")

                # -------- FINAL FAILURE --------
                if not result or (hasattr(result, "success") and not result.success):

                    self._escalate(
                        session_id, user_query, last_intent, "Multi-step failure"
                    )

                    state.final_response = (
                        "Your request has been escalated to a support agent."
                    )
                    state.metadata["execution"] = "escalated"

                    self.metrics.inc("requests_failure")
                    self.metrics.inc("requests_escalated")

                    self.inflight.set(key, state.final_response)

                    return state

                if hasattr(result, "data") and result.data is not None:
                    final_result = result

            # -------- TERMINATION GUARANTEE --------
            if not final_result:
                self._escalate(session_id, user_query, last_intent, "no_result")
                state.final_response = (
                    "Your request has been escalated to a support agent."
                )
                return state

            data = getattr(final_result, "data", None)

            if data is None:
                state.final_response = "Unable to retrieve details at the moment."

                self.inflight.set(key, state.final_response)

                return state

            if last_intent == "order_status":
                response = f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."
            elif last_intent == "refund_request":
                response = f"Refund status for order {data.get('order_id')} is {data.get('status')}."
            else:
                response = (
                    f"Ticket {data.get('ticket_id')} is currently {data.get('status')}."
                )

            state.final_response = response
            self.inflight.set(key, response)

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", response)

            latency = int((time.time() - start_time) * 1000)
            self.metrics.observe("total_latency", latency)

            self.metrics.inc("requests_success")

            if not response:
                response = "Unable to process request."

            return state
            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", state.final_response)

            # -------- LATENCY --------
            latency = int((time.time() - start_time) * 1000)
            self.metrics.observe("total_latency", latency)

            if not state.final_response:
                state.final_response = "Unable to process request."

            return state

        finally:
            if acquired:
                self.concurrent.release()

    # ================= STREAM =================
    def run_stream(self, user_query: str, session_id: str):
        key = None
        final_response = ""
        acquired = False

        try:
            if not self.rate_limiter.allow(session_id):
                yield "Too many requests. Please try again later."
                return

            # -------- GUARD 1 --------
            guard = self.guard.evaluate(user_query, "unknown")
            if not guard["allowed"]:
                yield "Your request cannot be processed due to security or validation constraints."
                return

            intent = self.classifier.classify(user_query)

            key = f"{session_id}:{self._normalize(user_query)}"

            if not self.inflight.set_if_absent(key):
                self.metrics.inc("dedup_hits")
                existing = self.inflight.get(key)
                if existing:
                    yield existing
                return

            if intent in [
                "order_status",
                "refund_request",
                "delivery_issue",
                "create_ticket",
            ]:
                route = "tool"
            else:
                tool_match = self.tool_selector.select(user_query)

                if tool_match:
                    route = "tool"
                    intent = tool_match
                else:
                    route = self.router.route(intent)

            cache_key = f"{intent}:{self._normalize(user_query)}"

            cached = self.semantic_cache.get(user_query)
            if cached:
                self.metrics.inc("semantic_cache_hits")
                self.inflight.set(key, cached)
                yield cached
                return
            else:
                self.metrics.inc("semantic_cache_misses")

            cached = self.cache.get(cache_key)
            if cached:
                self.metrics.inc("cache_hits")
                self.inflight.set(key, cached)
                yield cached
                return
            else:
                self.metrics.inc("cache_misses")

            # -------- GUARD 2 --------
            guard = self.guard.evaluate(user_query, intent)

            # -------- TOOL --------
            memory_context = self._get_memory_context(session_id)

            tasks = [user_query]

            final_response = ""

            last_intent = intent

            plan = None

            for task in tasks:

                # DO NOT reclassify core intents
                if intent in [
                    "order_status",
                    "refund_request",
                    "delivery_issue",
                    "create_ticket",
                ]:
                    sub_intent = intent
                else:
                    sub_intent = self.classifier.classify(task)

                last_intent = sub_intent

                plan = self._get_valid_plan(last_intent, task, memory_context)

                result = self.executor.execute(plan)

                if not result:
                    continue

                # -------- HANDLE RAG VIA PLAN (STREAM) --------
                response = None

                if result and hasattr(result, "data") and result.data is not None:
                    if isinstance(result.data, str):
                        response = result.data
                    elif isinstance(result.data, dict):
                        response = result.data.get("response")

                if plan.steps and plan.steps[0].action == "fallback_rag":
                    if not response:
                        response = "Unable..."
                    yield response
                    return

                if hasattr(result, "data") and last_intent == "order_status":
                    data = getattr(result, "data", None)

                    if data is None:
                        final_response = "Unable to retrieve details at the moment."
                        self.inflight.set(key, final_response)
                        yield final_response
                        return
                    final_response = f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."
                    break

                if hasattr(result, "success") and not result.success:

                    # -------- REFUND SPECIAL CASE --------
                    if last_intent == "refund_request":
                        final_response = "Refund cannot be processed because the order is not delivered yet."

                        self.inflight.set(key, final_response)

                        self.memory.add_message(session_id, "user", user_query)
                        self.memory.add_message(session_id, "assistant", final_response)

                        self.metrics.inc("requests_success")

                        yield final_response
                        return

                    # -------- OTHER FAILURES --------
                    reason = getattr(result, "error", "unknown_failure")

                    recovery_plan = self._replan_on_failure(
                        last_intent, task, reason, memory_context
                    )

                    if recovery_plan.steps != plan.steps:
                        result = self.executor.execute(recovery_plan)

                if not result or (hasattr(result, "success") and not result.success):

                    self._escalate(
                        session_id, user_query, last_intent, "Multi-step failure"
                    )

                    final_response = (
                        "Your request has been escalated to a support agent."
                    )

                    self.metrics.inc("requests_failure")
                    self.metrics.inc("requests_escalated")

                    self.inflight.set(key, final_response)

                    yield final_response
                    return

                data = getattr(result, "data", None)

                if data is None:
                    final_response = "Unable to retrieve details at the moment."

                    self.inflight.set(key, final_response)
                    yield final_response
                    return

                if last_intent == "order_status":
                    final_response = f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."
                elif last_intent == "refund_request":
                    final_response = f"Refund status for order {data.get('order_id')} is {data.get('status')}."
                else:
                    final_response = f"Ticket {data.get('ticket_id')} is currently {data.get('status')}."
            if not final_response:
                final_response = "Something went wrong."

            for ch in final_response:
                yield ch

            self.inflight.set(key, final_response)
            self.metrics.inc("requests_success")

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", final_response)

            if (
                final_response
                and len(final_response) > 20
                and "\n" in final_response
                and not final_response.startswith("[")
                and "escalated" not in final_response.lower()
                and "something went wrong" not in final_response.lower()
            ):
                self.semantic_cache.set(user_query, final_response)

            return

            self.inflight.delete(key)
            yield "Something went wrong."

        except Exception:
            if key:
                self.inflight.delete(key)
            yield "Something went wrong. Your request has been escalated."

        finally:
            if acquired:
                self.concurrent.release()

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

    def _get_valid_plan(self, intent, user_query, context=""):

        if intent == "order_status":
            return Plan([Step("get_order", {"query": user_query})], query=user_query)

        if intent == "refund_policy":
            return Plan(
                [Step("fallback_rag", {"query": user_query})],
                query=user_query,
            )

        if intent == "refund_request":

            if not re.search(r"ORD\d+", user_query.upper()):
                return Plan(
                    [Step("fallback_rag", {"query": user_query})],
                    query=user_query,
                )

            # ACTUAL REFUND FLOW
            return Plan(
                [
                    Step("get_order", {"query": user_query}),
                    Step("process_refund", {}),
                ],
                query=user_query,
            )

        if intent == "delivery_issue":
            return Plan(
                [
                    Step("get_order", {"query": user_query}),
                    Step("check_ticket", {}),
                    Step("create_or_fetch_ticket", {}),
                ],
                query=user_query,
            )

        if intent == "create_ticket":
            return Plan(
                [
                    Step("get_order", {"query": user_query}),
                    Step("check_ticket", {}),
                    Step("create_or_fetch_ticket", {}),
                ],
                query=user_query,
            )

        # only non-core intents use LLM planning
        plan = self.planner.create_plan(intent, user_query)
        plan, _ = self.plan_validator.validate(plan)

        if not plan:
            return Plan([Step("fallback_rag", {"query": user_query})], query=user_query)

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
