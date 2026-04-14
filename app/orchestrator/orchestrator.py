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
from app.cache.semantic_cache import SemanticCache
from app.rag.embedder import Embedder

from app.orchestrator.planner import Planner
from app.orchestrator.plan import Plan, Step
from app.orchestrator.executor import Executor
from app.orchestrator.plan_validator import PlanValidator
from app.orchestrator.decomposer import Decomposer
from app.orchestrator.response_composer import ResponseComposer

from app.tools.rag_tool import RAGTool

from app.core.error_mapper import ErrorMapper


import re
import time
import hashlib
import json


class Orchestrator:
    def __init__(self, tools, llm, rag):

        # -------- CORE --------
        self.tools = tools
        self.llm = llm
        self.rag = rag

        self.classifier = IntentClassifier()
        self.router = Router()

        self.memory = MemoryService()

        self.planner = Planner(self.llm)
        self.decomposer = Decomposer(self.llm)
        self.response_composer = ResponseComposer()

        self.guard = PolicyGuard()
        self.escalation = EscalationService()
        self.logger = Logger()

        self.cache = ResponseCache()
        self.rate_limiter = RateLimiter()
        self.inflight = InFlightRegistry()
        self.embedder = Embedder()
        self.semantic_cache = SemanticCache(self.embedder)
        self.concurrent = ConcurrencyLimiter(max_concurrent=5)

        self.llm_cb = CircuitBreaker()
        self.rag_cb = CircuitBreaker()

        self.llm_cb_stream = CircuitBreaker()
        self.rag_cb_stream = CircuitBreaker()

        self.metrics = Metrics()
        self.validator = ResponseValidator()

        # -------- EXECUTOR --------
        self.executor = Executor(self.tools)

        self.plan_validator = PlanValidator()

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

            # -------- DECOMPOSE --------
            if not self.llm_cb.allow():
                self.metrics.inc("llm_cb_block")
                tasks = [{"query": user_query, "type": "tool"}]
            else:
                try:
                    tasks = await self.decomposer.decompose(user_query)
                    self.llm_cb.record_success()
                except Exception:
                    self.llm_cb.record_failure()
                    tasks = [{"query": user_query, "type": "tool"}]
            print("DECOMPOSED_TASKS:", tasks)

            memory_context = self._get_memory_context(session_id)

            async def _safe_plan(t):
                if not self.llm_cb.allow():
                    self.metrics.inc("llm_cb_block")
                    return None

                try:
                    plan = await self.planner.create_plan(
                        self.classifier.classify(t["query"]),
                        t["query"],
                        memory_context,
                    )
                    self.llm_cb.record_success()
                    return plan

                except Exception:
                    self.llm_cb.record_failure()
                    return None

            plans = await asyncio.gather(*[_safe_plan(t) for t in tasks])

            validated = []
            for t, plan in zip(tasks, plans):
                if not plan:
                    continue
                plan, _ = self.plan_validator.validate(plan)
                if plan:
                    validated.append((t, plan))

            if not validated:
                parts = [p.strip() for p in user_query.split(" and ") if p.strip()]
                fallback_tasks = (
                    [{"query": p, "type": "tool"} for p in parts]
                    if parts
                    else [{"query": user_query, "type": "tool"}]
                )

                validated = []
                for t in fallback_tasks:
                    try:
                        plan = await self.planner.create_plan(
                            self.classifier.classify(t["query"]),
                            t["query"],
                            memory_context,
                        )
                        plan, _ = self.plan_validator.validate(plan)
                        if plan:
                            validated.append((t, plan))
                    except:
                        continue

            print("FINAL_VALIDATED:", [t for t, _ in validated])

            state.metadata["plans"] = []

            # -------- EXECUTION UNIT --------
            async def _run_task(plan, original_query):

                is_rag = any(step.action == "rag" for step in plan.steps)

                # -------- CIRCUIT GUARD (EARLY) --------
                if is_rag and not self.rag_cb.allow():
                    self.metrics.inc("rag_cb_block")
                    return None

                cache_key = self._plan_cache_key(plan)
                owner = self.inflight.set_if_absent(cache_key)

                # -------- INFLIGHT WAIT --------
                if not owner:
                    self.metrics.inc("inflight_wait")

                    for _ in range(20):
                        cached = self.inflight.get(cache_key)
                        if cached is not None:
                            return cached
                        await asyncio.sleep(0.1)

                    return None

                try:
                    semantic_key = original_query.lower().strip()

                    # -------- L1: SEMANTIC CACHE --------
                    semantic_cached = self.semantic_cache.get(semantic_key)
                    if semantic_cached:
                        self.metrics.inc("semantic_hit")

                        final = {"_tool": "rag", "response": semantic_cached}
                        self.inflight.set(cache_key, final)
                        return final

                    # -------- L2: REDIS CACHE --------
                    cached = self.cache.get(cache_key)
                    if cached:
                        self.metrics.inc("cache_hit")

                        self.inflight.set(cache_key, cached)
                        return cached

                    # -------- MISS --------
                    self.metrics.inc("cache_miss")
                    self.metrics.inc("execution_start")

                    # -------- EXECUTION --------
                    try:
                        if is_rag:
                            try:
                                result = await asyncio.wait_for(
                                    self.executor.execute_parallel(plan),
                                    timeout=6,
                                )
                            except asyncio.TimeoutError:
                                self.metrics.inc("execution_timeout")
                                self.rag_cb.record_failure()
                                return None
                            except Exception:
                                self.metrics.inc("execution_error")
                                self.rag_cb.record_failure()
                                return None
                        else:
                            result = await self.executor.execute_parallel(plan)

                    except Exception:
                        self.metrics.inc("execution_error")
                        return None

                    # -------- FAILURE --------
                    if not result or not result.success:
                        self.metrics.inc("execution_error")

                        if is_rag:
                            self.rag_cb.record_failure()

                        err = (
                            getattr(result, "error", "unknown_failure")
                            if result
                            else "no_result"
                        )

                        if err == "Order not found":
                            return {"_tool": "order", "response": "Order not found."}

                        return None

                    self.metrics.inc("execution_success")
                    data = result.data

                    # -------- NORMALIZATION --------
                    if isinstance(data, dict) and "steps" in data:
                        final = {
                            "steps": [
                                (
                                    {"_tool": "rag", "response": s["response"]}
                                    if s.get("_tool") == "rag" and s.get("response")
                                    else s
                                )
                                for s in data["steps"]
                            ]
                        }

                    elif isinstance(data, dict) and data.get("_tool") == "rag":
                        final = (
                            data
                            if data.get("response")
                            else {
                                "_tool": "rag",
                                "response": "No relevant information found.",
                            }
                        )

                    elif isinstance(data, str):
                        final = {"_tool": "rag", "response": data}

                    elif isinstance(data, dict) and "response" in data:
                        final = {"_tool": "rag", "response": data["response"]}

                    else:
                        final = None

                    # -------- STORE --------
                    if final:
                        self.cache.set(cache_key, final)
                        self.metrics.inc("cache_store")

                        if is_rag:
                            self.rag_cb.record_success()

                            if final.get("_tool") == "rag" and final.get("response"):
                                self.semantic_cache.set(semantic_key, final["response"])
                                self.metrics.inc("semantic_store")
                    else:
                        if is_rag:
                            self.rag_cb.record_failure()

                    self.inflight.set(cache_key, final)
                    return final

                finally:
                    if owner:
                        self.inflight.delete(cache_key)

            # -------- SPLIT --------
            tool_tasks, rag_tasks = [], []

            for t, plan in validated:
                state.metadata["plans"].append([str(step) for step in plan.steps])

                if t["type"] == "rag":
                    rag_tasks.append(_run_task(plan, t["query"]))
                else:
                    tool_tasks.append(_run_task(plan, t["query"]))

            # -------- EXECUTE --------
            tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)
            rag_results = (
                await asyncio.gather(*rag_tasks, return_exceptions=True)
                if rag_tasks
                else []
            )

            results = tool_results + rag_results

            # -------- MERGE --------
            all_results = []
            for res in results:
                if isinstance(res, Exception) or not res:
                    continue

                if isinstance(res, dict) and "steps" in res:
                    all_results.extend(res["steps"])
                    continue

                if isinstance(res, dict) and "_tool" not in res and "response" in res:
                    res["_tool"] = "rag"

                all_results.append(res)

            # -------- RESPONSE --------
            structured = self.response_composer.compose(all_results, state.intent)

            response = structured["summary"]

            # -------- GLOBAL FAILURE DETECTION --------
            if not all_results:
                self.metrics.inc("execution_error")

                return _exit("Unable to process request.", "failure", "empty_response")

            state.metadata["details"] = structured["details"]

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", response)

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

    def _plan_cache_key(self, plan: Plan):
        steps = [
            {
                "action": step.action,
                "params": step.params,
            }
            for step in plan.steps
        ]

        raw = json.dumps(steps, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()
