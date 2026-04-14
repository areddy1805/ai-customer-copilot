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

        self.rag = RAGService(self.llm)
        self.planner = Planner(self.llm)
        self.decomposer = Decomposer(self.llm)

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

        self.executor = Executor(
            {
                "order": self.order_tool,
                "refund": self.refund_tool,
                "ticket": self.ticket_tool,
                "rag": self,
            }
        )

        self.plan_validator = PlanValidator()

        # self.semantic_cache.store = []
        self.session_state = {}

    # ================= RUN =================

    async def run(self, user_query: str, session_id: str) -> ConversationState:
        self.metrics.inc("requests_total")
        start_time = time.time()

        state = ConversationState(user_query=user_query)
        trace_id = str(uuid.uuid4())
        state.metadata["trace_id"] = trace_id

        cache_key = f"{session_id}:{user_query}"

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

            if error:
                mapped = ErrorMapper.map(error)
                self.metrics.inc(f"error_type_{mapped['error_type']}")
                self.metrics.inc(f"error_code_{mapped['error_code']}")

            self.metrics.observe("total_latency", latency)

            self.logger.log_request(
                session_id=session_id,
                user_query=user_query,
                intent=state.intent,
                route=state.metadata.get("route"),
                plans=state.metadata.get("plans"),
                tools_used=self._extract_tools(state.metadata.get("plans")),
                latency_ms=latency,
                status=status,
                error=error,
            )

            if clear_session:
                self.session_state.pop(session_id, None)

            return state

        try:
            # -------- RATE LIMIT --------
            if not self.rate_limiter.allow(session_id):
                return _exit("Too many requests.", "failure", "rate_limit")

            # -------- GUARD --------
            guard = self.guard.evaluate(user_query, "unknown")
            if not guard["allowed"]:
                return _exit("Request blocked.", "failure", "guard_block")

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
                return _exit("Connecting to agent.", "failure", "user_requested_human")

            # -------- INTENT --------
            intent = self.classifier.classify(user_query)
            state.intent = intent
            state.metadata["route"] = "agentic"
            self.metrics.inc(f"intent_{intent}")

            print("ENTERING AGENTIC FLOW")

            # -------- DECOMPOSITION --------
            tasks = await self.decomposer.decompose(user_query)
            print("DECOMPOSED_TASKS:", tasks)

            if not tasks:
                parts = [p.strip() for p in user_query.split(" and ") if p.strip()]
                tasks = (
                    [{"query": p, "type": "tool"} for p in parts]
                    if parts
                    else [{"query": user_query, "type": "tool"}]
                )

            print("FINAL_TASKS:", tasks)

            memory_context = self._get_memory_context(session_id)

            state.metadata["plans"] = []
            all_results = []

            # -------- EXECUTION --------
            async def _run_task(task_query):
                task_intent = self.classifier.classify(task_query)

                plan = await self.planner.create_plan(
                    task_intent, task_query, memory_context
                )

                plan, error = self.plan_validator.validate(plan)
                if not plan:
                    return {"response": "Unable to process request."}

                state.metadata["plans"].append([str(step) for step in plan.steps])

                result = await asyncio.wait_for(
                    self.executor.execute_parallel(plan), timeout=5
                )

                if not result or not result.success:
                    err = (
                        getattr(result, "error", "unknown_failure")
                        if result
                        else "no_result"
                    )

                    if err == "Order not found":
                        return {"response": f"Order not found."}

                    return {"response": "Unable to process request."}

                return result.data

            results = await asyncio.gather(*[_run_task(t["query"]) for t in tasks])

            # -------- RESPONSE BUILD --------
            responses = []

            for res in results:
                if "steps" in res:
                    for step in res["steps"]:
                        all_results.append(step)
                else:
                    all_results.append(res)

            for data in all_results:
                tool = data.get("_tool")

                if tool == "order":
                    responses.append(
                        f"Order {data.get('order_id')} is {data.get('status')}."
                    )
                elif tool == "refund":
                    responses.append(
                        f"Refund for {data.get('order_id')} is {data.get('status')}."
                    )
                elif tool == "ticket":
                    responses.append(
                        f"Ticket {data.get('ticket_id')} is {data.get('status')}."
                    )
                elif "response" in data:
                    responses.append(data["response"])

            response = (
                " ".join(responses) if responses else "Unable to process request."
            )

            # -------- MEMORY --------
            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", response)

            # -------- CACHE (AFTER SUCCESS ONLY) --------
            if response and "Unable" not in response:
                self.cache.set(cache_key, response)

            return _exit(response, clear_session=True)

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
