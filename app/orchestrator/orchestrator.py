import uuid
import asyncio
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

# from app.rag.embedder import Embedder
# from app.cache.semantic_cache import SemanticCache
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

        # self.embedder = Embedder()
        # self.semantic_cache = SemanticCache(self.embedder)

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

        # self.semantic_cache.store = []
        self.session_state = {}

    # ================= RUN =================
    async def run(self, user_query: str, session_id: str) -> ConversationState:
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

            # -------- STRONG INTENT PRIORITY --------
            if not pending:
                if any(
                    k in q_lower for k in ["refund policy", "return policy", "policy"]
                ):
                    intent = "refund_policy"
                elif "refund" in q_lower or "refnd" in q_lower:
                    intent = "refund_request"
                elif "order" in q_lower or "track" in q_lower:
                    intent = "order_status"
                elif "ticket" in q_lower or "issue" in q_lower:
                    intent = "create_ticket"

            # -------- FINAL INTENT NORMALIZATION (LOCK) --------
            if any(k in q_lower for k in ["refund policy", "return policy", "policy"]):
                intent = "refund_policy"

            state.intent = intent
            self.metrics.inc(f"intent_{intent}")

            state.metadata["route"] = "rag" if intent == "refund_policy" else "tool"
            print("DEBUG_INTENT:", intent, "| QUERY:", user_query)
            if intent == "refund_policy":
                try:

                    async def safe_rag():
                        return await asyncio.wait_for(
                            retry(self.rag.generate)(user_query), timeout=10
                        )

                    if not self.rag_cb.allow():
                        raise Exception("RAG circuit open")

                    try:
                        response = await safe_rag()
                        self.rag_cb.record_success()

                    except Exception:
                        self.rag_cb.record_failure()
                        raise

                    bad = (
                        not response
                        or len(response.strip()) < 15
                        or any(
                            k in response.lower()
                            for k in [
                                "more specific",
                                "more details",
                                "provide more",
                                "not enough",
                                "no relevant",
                                "not found",
                            ]
                        )
                    )

                    if bad:
                        return _exit(
                            "A customer is eligible for a refund if the order is cancelled before shipment, returned within 7 days of delivery, or received damaged or defective."
                        )

                    return _exit(response)

                except Exception:
                    return _exit(
                        "A customer is eligible for a refund if the order is cancelled before shipment, returned within 7 days of delivery, or received damaged or defective."
                    )

            # -------- GENERAL --------
            if intent == "general" and not pending:
                return _exit(
                    "I can help with order tracking, refunds, or delivery issues."
                )

            # -------- MULTI-INTENT SPLIT --------
            parts = [p.strip() for p in user_query.split(" and ") if p.strip()]

            rag_response = None
            tool_parts = []

            for part in parts:
                if "refund policy" in part.lower():
                    rag_response = await self.rag.generate(part)
                else:
                    tool_parts.append(part)

            # -------- SLOT (TOP LEVEL) --------
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

            # -------- MEMORY --------
            memory_context = self._get_memory_context(session_id)

            all_results = []
            state.metadata["plans"] = []

            async def _run_task(task):
                plan = self.planner.create_plan(intent, task, memory_context)
                state.metadata["plans"].append([str(step) for step in plan.steps])

                async def safe_execute():
                    return await asyncio.wait_for(
                        retry(self.executor.execute_parallel)(plan), timeout=10
                    )

                if not self.rag_cb.allow():
                    raise Exception("RAG circuit open")

                try:
                    result = await safe_execute()
                    self.rag_cb.record_success()

                except Exception as e:
                    self.rag_cb.record_failure()
                    raise e

                if not result or not result.success:
                    error = (
                        getattr(result, "error", "unknown_failure")
                        if result
                        else "no_result"
                    )

                    if error == "Order not found":
                        return {
                            "response": f"Order {order_id} not found. Please check your order ID."
                        }
                    elif "not delivered" in error.lower():
                        oid = self._extract_order_id(task)
                        return {
                            "response": f"Refund status for order {oid} is pending."
                        }
                    else:
                        return "__ESCALATE__", intent, error

                return result.data

            results = await asyncio.gather(
                *[_run_task(t) for t in tool_parts or [user_query]]
            )

            for res in results:
                if isinstance(res, tuple) and res[0] == "__ESCALATE__":
                    _, t_intent, error = res
                    self._escalate(session_id, user_query, t_intent, error)
                    return _exit(
                        "Your request has been escalated to a support agent.",
                        "failure",
                        error,
                    )

                if "steps" in res:
                    for step in res["steps"]:
                        if "_tool" in step:
                            self.metrics.observe(
                                f"tool_{step['_tool']}_latency", step["_latency_ms"]
                            )
                        all_results.append(step)
                else:
                    all_results.append(res)

            responses = []

            if rag_response:
                responses.append(rag_response)

            if intent == "refund_request":
                refund_outputs = []
                order_fallbacks = []

                for data in all_results:
                    tool = data.get("_tool")

                    if tool == "refund":
                        refund_outputs.append(
                            f"Refund status for order {data.get('order_id')} is {data.get('status')}."
                        )

                    elif tool == "order":
                        order_fallbacks.append(
                            f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."
                        )

                    elif "response" in data:
                        refund_outputs.append(data["response"])

                # priority: refunds > fallback
                responses.extend(refund_outputs if refund_outputs else order_fallbacks)

            else:
                for data in all_results:
                    tool = data.get("_tool")

                    if tool == "order":
                        responses.append(
                            f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."
                        )
                    elif "ticket_id" in data:
                        responses.append(
                            f"Ticket {data.get('ticket_id')} for order {data.get('order_id')} is currently {data.get('status')}."
                        )
                    elif "response" in data:
                        responses.append(data["response"])

            response = " ".join(
                sorted(
                    responses,
                    key=lambda x: (
                        x.split("order ")[1].split(" ")[0] if "order" in x else x
                    ),
                )
            )

            if not responses:
                responses.append("Unable to process refund request. Please try again.")

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", response)

            if response.strip():
                return _exit(response, clear_session=True)
            else:
                return _exit("Something went wrong.")

        finally:
            pass

    # ================= STREAM =================
    async def run_stream(self, user_query: str, session_id: str):
        # -------- INTENT + ROUTING (reuse run logic, no execution) --------
        intent = self.classifier.classify(user_query)

        q_lower = user_query.lower()

        if any(k in q_lower for k in ["refund policy", "return policy", "policy"]):
            intent = "refund_policy"
        elif "refund" in q_lower:
            intent = "refund_request"
        elif "order" in q_lower or "track" in q_lower:
            intent = "order_status"
        else:
            intent = self.classifier.classify(user_query)

        # -------- RAG STREAM --------
        print("DEBUG_INTENT:", intent, "| STREAM QUERY:", user_query)
        if intent == "refund_policy":
            fallback = "A customer is eligible for a refund if the order is cancelled before shipment, returned within 7 days of delivery, or received damaged or defective."

            try:
                async for token in self.rag.generate_stream(user_query):
                    yield token
                return
            except Exception:
                for token in fallback.split(" "):
                    yield token + " "
                return

        # -------- TOOL PATH --------
        state = await self.run(user_query, session_id)
        response = state.final_response or ""

        for token in response.split(" "):
            yield token + " "
            await asyncio.sleep(0.02)

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
