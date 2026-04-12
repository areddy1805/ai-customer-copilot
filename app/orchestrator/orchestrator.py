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
from app.orchestrator.plan_schema import Plan, Step
from app.orchestrator.executor import Executor
from app.orchestrator.plan_validator import PlanValidator
from app.orchestrator.decomposer import TaskDecomposer

from app.core.error_mapper import ErrorMapper

from app.agent.planner import AgentPlanner
from app.agent.validator import PlanValidator as AgentPlanValidator
from app.core.error_map import map_error_message


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
        self.decomposer = TaskDecomposer()

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

        all_results = []

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

            state.metadata["execution_trace"] = all_results

            self.logger.log_request(
                session_id=session_id,
                user_query=user_query,
                intent=state.intent,
                route=state.metadata.get("route"),
                plans=state.metadata.get("plans"),
                execution_trace=all_results,
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
                return _exit("Request blocked due to policy.", "failure", "guard_block")

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

            # -------- QUERY DECOMPOSER --------
            tasks = self.decomposer.decompose(user_query)

            if not tasks:
                return _exit("Unable to understand request.", "failure")

            state.intent = "multi_intent"
            self.metrics.inc("intent_multi_intent")
            state.metadata["route"] = "tool"

            # -------- PLAN --------
            try:
                plan = self._get_deterministic_plan(tasks)

                if self.agent_enabled:
                    try:
                        optimized_plan = self.agent_planner.optimize(plan, tasks)

                        self.agent_validator.validate(optimized_plan)

                        plan = optimized_plan

                    except Exception:
                        pass
                else:
                    raise ValueError("Agent disabled")

            except Exception:
                plan = self._get_deterministic_plan(tasks)
                self.metrics.inc("plan_fallback")

            try:
                plan.trace_id = trace_id
            except Exception:
                pass

            self.metrics.inc("steps_total", len(plan.steps))

            state.metadata["plans"] = [
                [
                    {
                        "step_id": s.step_id,
                        "tool": s.tool_name,
                        "depends_on": s.depends_on,
                    }
                    for s in plan.steps
                    if s.action == "tool"
                ]
            ]

            # -------- EXECUTION --------
            def _run_async(coro):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        return asyncio.ensure_future(coro)
                except RuntimeError:
                    pass
                return asyncio.run(coro)

            result = _run_async(self.executor.execute_dag(plan))

            if asyncio.isfuture(result):
                result = asyncio.get_event_loop().run_until_complete(result)

            if hasattr(result, "data"):
                result = result.data

            if isinstance(result, dict) and "steps" in result:
                for step in result["steps"]:
                    if "_tool" in step:
                        self.metrics.observe(
                            f"tool_{step['_tool']}_latency",
                            step.get("_latency_ms", 0),
                        )
                    all_results.append(step)

            # enforce deterministic order
            all_results = sorted(all_results, key=lambda x: x.get("_step_id", 0))

            # -------- RESPONSE BUILD --------
            responses = []
            seen = set()
            grouped = {}

            # -------- GROUP BY ORDER --------
            for data in all_results:
                if not isinstance(data, dict):
                    continue

                oid = data.get("order_id")
                if not oid:
                    continue

                grouped.setdefault(oid, []).append(data)

            # -------- BUILD DETERMINISTIC RESPONSE --------
            from app.core.errors import ErrorCode

            for oid, events in grouped.items():

                for data in events:
                    tool = data.get("_tool")
                    code = data.get("error_code")

                    # -------- ORDER --------
                    if tool == "get_order":

                        if code == ErrorCode.DEPENDENCY_FAILED:
                            continue

                        if code == ErrorCode.ORDER_NOT_FOUND:
                            msg = f"Order {oid}: Order not found"

                        elif code:
                            msg = f"Order {oid}: Unable to fetch order details"

                        else:
                            msg = f"Your order {oid} is {data.get('status')} and expected by {data.get('delivery_eta')}."

                    # -------- REFUND --------
                    elif tool == "refund":

                        if code == ErrorCode.DEPENDENCY_FAILED:
                            continue

                        if code == ErrorCode.ORDER_NOT_FOUND:
                            msg = f"Order {oid}: Order not found"

                        elif code == ErrorCode.REFUND_NOT_ALLOWED:
                            msg = f"Order {oid}: Refund cannot be processed until delivery is complete"

                        elif code == ErrorCode.PAYMENT_NOT_FOUND:
                            msg = f"Order {oid}: Payment record not found"

                        elif code:
                            msg = f"Order {oid}: Refund failed"

                        else:
                            msg = f"Order {oid}: Refund {data.get('status')}"

                    # -------- TICKET --------
                    elif tool == "create_ticket":

                        if code:
                            msg = f"Order {oid}: Unable to create support ticket"
                        else:
                            msg = f"Ticket {data.get('ticket_id')} for order {oid} is {data.get('status')}."

                    # -------- RAG --------
                    elif "response" in data:
                        msg = data["response"]

                    else:
                        continue

                    if msg not in seen:
                        seen.add(msg)
                        responses.append(msg)

            # -------- LLM RECOVERY (STRICT + LIGHTWEIGHT) --------
            known_errors = {
                "Refund not allowed: Order not delivered",
                "Order not found",
            }

            failed = [
                {
                    "order_id": d.get("order_id"),
                    "error": d.get("error"),
                }
                for d in all_results
                if isinstance(d, dict)
                and d.get("_status") == "failed"
                and d.get("error") not in known_errors
            ]

            if failed and len(failed) <= 1:  # HARD LIMIT
                try:
                    llm_response = self.llm.generate(
                        task=TaskType.RECOVERY, query=user_query, context=str(failed)
                    )

                    if llm_response:
                        responses.append(f"\nNote: {llm_response.strip()}")

                except Exception:
                    pass

            # -------- FINAL --------
            response = (
                "\n".join(responses) if responses else "Unable to process request."
            )

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", response)

            return _exit(response, clear_session=True)

        finally:
            pass

    # ---------------- STREAM ----------------
    def run_stream(self, user_query: str, session_id: str):
        state = self.run(user_query, session_id)
        for token in (state.final_response or "").split(" "):
            yield token + " "
            # time.sleep(0.02)

    # ---------------- HELPERS ----------------
    def _extract_order_id(self, query: str):
        match = re.search(r"ORD0*(\d+)", query.upper())
        return f"ORD{int(match.group(1))}" if match else None

    def _escalate(self, session_id, user_query, intent, reason):
        self.escalation.push(
            session_id=session_id,
            user_query=user_query,
            intent=intent,
            reason=reason,
        )

    def _get_deterministic_plan(self, tasks):

        from app.orchestrator.plan_schema import Plan, Step

        steps = []
        step_id = 1

        for task in tasks:
            intent = task["intent"]
            oid = task["order_id"]

            # -------- ORDER --------
            if intent == "order_status":
                steps.append(Step(step_id, "tool", "get_order", {"order_id": oid}, []))
                step_id += 1

            # -------- REFUND --------
            elif intent == "refund_request":

                get_id = step_id

                steps.append(Step(get_id, "tool", "get_order", {"order_id": oid}, []))
                step_id += 1

                steps.append(
                    Step(
                        step_id,
                        "tool",
                        "refund",
                        {"order_id": oid},
                        [get_id],
                    )
                )
                step_id += 1

            # -------- TICKET --------
            elif intent == "create_ticket":

                get_id = step_id

                steps.append(Step(get_id, "tool", "get_order", {"order_id": oid}, []))
                step_id += 1

                steps.append(
                    Step(
                        step_id,
                        "tool",
                        "create_ticket",
                        {"order_id": oid, "issue": "delivery_issue"},
                        [get_id],
                    )
                )
                step_id += 1

            # -------- FALLBACK --------
            else:
                steps.append(
                    Step(step_id, "tool", "fallback_rag", {"query": str(task)}, [])
                )
                step_id += 1

        return Plan(steps, query=str(tasks))

    def _get_memory_context(self, session_id, limit=5):
        history = self.memory.get_history(session_id)
        if not history:
            return ""
        return "\n".join(f"{m['role']}: {m['content']}" for m in history[-limit:])

    def query(self, query: str):
        from app.orchestrator.executor import ToolResult

        return ToolResult(success=True, data={"response": self.rag.generate(query)})

    def _normalize_agent_plan(self, plan, query):

        import re
        from app.orchestrator.plan_schema import Plan, Step

        if not plan or not plan.steps:
            raise ValueError("Invalid agent plan")

        order_ids = list(dict.fromkeys(re.findall(r"ORD\d+", query.upper())))

        steps = []
        step_id = 1

        query_lower = query.lower()
        parts = [p.strip() for p in query_lower.split("and") if p.strip()]

        for oid in order_ids:

            get_id = step_id
            steps.append(Step(get_id, "tool", "get_order", {"order_id": oid}, []))
            step_id += 1

            is_refund = any(oid.lower() in part and "refund" in part for part in parts)

            if is_refund:
                steps.append(
                    Step(
                        step_id,
                        "tool",
                        "refund",
                        {"order_id": oid},
                        [get_id],
                    )
                )
                step_id += 1
                continue

            is_ticket = any(
                oid.lower() in part and ("ticket" in part or "issue" in part)
                for part in parts
            )

            if is_ticket:
                steps.append(
                    Step(
                        step_id,
                        "tool",
                        "create_ticket",
                        {"order_id": oid, "issue": "delivery_issue"},
                        [get_id],
                    )
                )
                step_id += 1

        if not steps:
            steps.append(Step(step_id, "tool", "fallback_rag", {"query": query}, []))

        return Plan(steps, query=query)
