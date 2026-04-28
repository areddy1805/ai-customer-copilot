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
from app.observability.request_metrics import RequestMetrics
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

    MAX_AGENT_STEPS = 2

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
        req_metrics = RequestMetrics(request_id=trace_id, query=user_query)

        req_metrics.llm_provider = type(self.llm).__name__
        req_metrics.embedding_provider = "local"
        req_metrics.search_provider = "local"

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

            req_metrics.success = status == "success"
            req_metrics.error = error or ""
            req_metrics.llm_ms = req_metrics.decomposer_ms + sum(req_metrics.planner_ms)
            req_metrics.finalize()

            state.metadata["trace"] = state.trace

            # LATENCY BREAKDOWN
            state.metadata["latency_breakdown"] = {
                "planner_time": sum(state.trace.get("planner_ms", [])),
                "decomposer_time": state.trace.get("decomposer_ms", 0),
                "executor_time": sum(state.trace.get("executor_ms", [])),
                "total_time": latency,
            }

            state.metadata["metrics"] = req_metrics.to_dict()

            return state

        try:
            # -------- RATE LIMIT --------
            is_eval = session_id == "eval"

            if not is_eval and not self.rate_limiter.allow(session_id):
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

            # -------- RESPONSE CACHE (PRE-LLM) --------
            cache_key = user_query.strip().lower()
            is_eval = session_id == "eval"

            cached_response = None
            if not is_eval:
                cached_response = self.cache.get(cache_key)

            if cached_response:
                req_metrics.response_cache_hit = True
                req_metrics.llm_calls = 0
                req_metrics.llm_ms = 0

                state.intent = self.classifier.classify(user_query)
                state.metadata["route"] = "cache"
                state.metadata["plans"] = []

                state.metadata["details"] = cached_response.get("details", [])

                state.trace["cache"]["cache_hit"] = True

                return _exit(cached_response["response"])

            # -------- INTENT --------
            intent = self.classifier.classify(user_query)
            state.intent = intent
            state.metadata["route"] = "agentic"
            self.metrics.inc(f"intent_{intent}")

            # -------- DECOMPOSE --------
            if not self.llm_cb.allow():
                self.metrics.inc("llm_cb_block")
                tasks = [{"query": user_query, "type": "tool"}]
                req_metrics.llm_cb_triggered = True
                req_metrics.fallback_triggered = True
            else:
                start = time.time()
                try:
                    tasks = await self.decomposer.decompose(user_query)
                    # ---- FIX: upgrade dependent rag → tool ----
                    for t in tasks:
                        q = t["query"].lower()

                        if "refund" in q or "cancel" in q:
                            t["type"] = "tool"

                    latency = int((time.time() - start) * 1000)
                    req_metrics.llm_ms += latency
                    self.metrics.observe("latency_decomposer", latency)
                    state.trace["decomposer_ms"] = latency
                    self.llm_cb.record_success()
                    req_metrics.decomposer_ms = latency
                    req_metrics.llm_calls += 1
                except Exception:
                    latency = int((time.time() - start) * 1000)
                    req_metrics.llm_ms += latency
                    self.metrics.observe("latency_decomposer", latency)
                    state.trace["decomposer_ms"] = latency
                    self.llm_cb.record_failure()
                    req_metrics.decomposer_ms = latency
                    req_metrics.llm_calls += 1
                    req_metrics.fallback_triggered = True
                    tasks = [{"query": user_query, "type": "tool"}]

            memory_context = self._get_memory_context(session_id)

            validated = []

            # -------- PASS 1: CREATE + VALIDATE --------
            for t in tasks:
                if not self.llm_cb.allow():
                    self.metrics.inc("llm_cb_block")
                    req_metrics.llm_cb_triggered = True
                    continue

                start = time.time()
                try:
                    plan = await self.planner.create_plan(
                        self.classifier.classify(t["query"]),
                        t["query"],
                        memory_context,
                    )
                    latency = int((time.time() - start) * 1000)
                    req_metrics.llm_ms += latency
                    self.metrics.observe("latency_planner", latency)
                    state.trace["planner_ms"].append(latency)
                    self.llm_cb.record_success()
                    req_metrics.planner_ms.append(latency)
                    req_metrics.llm_calls += 1
                except Exception:
                    latency = int((time.time() - start) * 1000)
                    req_metrics.llm_ms += latency
                    self.metrics.observe("latency_planner", latency)
                    state.trace["planner_ms"].append(latency)
                    self.llm_cb.record_failure()
                    req_metrics.planner_ms.append(latency)
                    req_metrics.llm_calls += 1
                    req_metrics.fallback_triggered = True
                    continue

                plan, err = self.plan_validator.validate(plan)

                if not plan:
                    plan = Plan([Step(action="rag", params={"query": t["query"]})])

                validated.append((t, plan))

            # -------- PASS 2: DEPENDENCY RESOLUTION --------
            for i, (t, plan) in enumerate(validated):

                for step in plan.steps:

                    # ---- EXTRACT ----
                    order_id = self._extract_order_id(t["query"])

                    # ---- INHERIT (ONLY FROM PREVIOUS INDEX) ----
                    if not order_id:
                        for j in range(i):
                            prev_plan = validated[j][1]
                            for s in prev_plan.steps:
                                if s.params.get("order_id"):
                                    order_id = s.params["order_id"]
                                    break
                            if order_id:
                                break

                    # ---- FORCE TOOL IF ORDER_ID EXISTS ----
                    if order_id:
                        if step.action in ["refund", "order", "rag"]:
                            # upgrade rag → refund if intent implies refund
                            if "refund" in t["query"].lower():
                                step.action = "refund"
                            elif (
                                "cancel" in t["query"].lower()
                                or "order" in t["query"].lower()
                            ):
                                step.action = "order"

                            step.params = {"order_id": order_id}

                    else:
                        if step.action in ["refund", "order"]:
                            step.action = "rag"
                            step.params = {"query": t["query"]}

                    # ---- NORMALIZE ----
                    if "order_id" in step.params and step.params["order_id"]:
                        raw = str(step.params["order_id"]).strip().upper()
                        match = re.search(r"(\d+)", raw)
                        if match:
                            step.params["order_id"] = f"ORD{int(match.group(1))}"

            state.metadata["plans"] = []

            # -------- EXECUTION UNIT --------
            async def _run_task(plan, original_query):
                is_rag = any(step.action == "rag" for step in plan.steps)

                tool_name = plan.steps[0].action if plan.steps else "unknown"

                step = plan.steps[0]

                # -------- RAG DIRECT EXECUTION --------
                if step.action == "rag":
                    try:
                        response = await self.rag.generate(original_query)

                        return [
                            {"_tool": "rag", "response": response, "status": "success"}
                        ]
                    except Exception as e:
                        return [{"_tool": "rag", "status": "failed", "reason": str(e)}]

                cache_key = self._plan_cache_key(plan)
                owner = self.inflight.set_if_absent(cache_key)

                if is_rag:
                    req_metrics.rag_calls += 1

                if not owner:
                    for _ in range(20):
                        cached = self.inflight.get(cache_key)
                        if cached is not None:
                            return cached
                        await asyncio.sleep(0.1)
                    return None

                try:
                    # -------- CACHE --------
                    cached = None
                    if not is_eval:
                        cached = self.cache.get(cache_key)

                    if cached:
                        state.trace["cache"]["cache_hit"] = True
                        req_metrics.response_cache_hit = True
                        state.trace["executor_ms"].append(0)
                        state.trace["tools"].append(tool_name)
                        return cached

                    # -------- EXECUTION --------
                    start_exec = time.time()

                    result = await self.executor.execute_parallel(plan)

                    latency = int((time.time() - start_exec) * 1000)

                    state.trace["executor_ms"].append(latency)
                    state.trace["tools"].append(tool_name)
                    state.trace["cache"]["executed"] = True
                    req_metrics.executor_ms.append(latency)
                    req_metrics.tool_calls += 1
                    req_metrics.tools_used.append(tool_name)

                    # -------- FAILURE --------
                    if not result or not result.success:
                        err = getattr(result, "error", "unknown")
                        req_metrics.fallback_triggered = True

                        return {
                            "_tool": tool_name,
                            "order_id": plan.steps[0].params.get("order_id"),
                            "status": "failed",
                            "reason": err,
                        }

                    # -------- SUCCESS --------
                    data = result.data

                    if isinstance(data, dict) and "steps" in data:
                        final = data["steps"]
                    else:
                        final = [data]

                    self.cache.set(cache_key, final)

                    return final

                finally:
                    if owner:
                        self.inflight.delete(cache_key)

            # -------- AGENT LOOP --------
            all_results = []
            state.trace["iterations"] = []

            # -------- TASK ORDER (USER INTENT ORDER) --------
            task_order = {}

            for idx, (t, plan) in enumerate(validated):
                action = plan.steps[0].action if plan.steps else "unknown"
                order_id = plan.steps[0].params.get("order_id")
                task_order[(action, order_id)] = idx

            def _key(x):
                return (x.get("_tool"), x.get("order_id"), x.get("ticket_id"))

            for step_idx in range(self.MAX_AGENT_STEPS):

                iteration_trace = {"step": step_idx, "plans": [], "results": []}

                # -------- PLAN ORDERING (DEPENDENCY) --------
                ordered_tasks = []
                deferred_tasks = []

                for t, plan in validated:
                    state.metadata["plans"].append([str(step) for step in plan.steps])

                    # -------- NORMALIZE PLAN FOR TRACE --------
                    for step in plan.steps:
                        if "order_id" in step.params and step.params["order_id"]:
                            raw = step.params["order_id"].strip().upper()

                            match = re.search(r"ORD0*(\d+)", raw)
                            if match:
                                step.params["order_id"] = f"ORD{int(match.group(1))}"

                    iteration_trace["plans"].append([str(step) for step in plan.steps])

                    action = plan.steps[0].action if plan.steps else "unknown"

                    if action == "order":
                        ordered_tasks.append((t, plan))
                    elif action == "refund":
                        deferred_tasks.append((t, plan))
                    else:
                        ordered_tasks.append((t, plan))

                iteration_results = []

                # -------- EXECUTE ORDER TASKS --------
                for t, plan in ordered_tasks:
                    res = await _run_task(plan, t["query"])

                    if isinstance(res, list):
                        iteration_results.extend(res)
                    elif res:
                        iteration_results.append(res)

                # -------- EXECUTE DEFERRED TASKS --------
                for t, plan in deferred_tasks:
                    res = await _run_task(plan, t["query"])

                    if isinstance(res, list):
                        iteration_results.extend(res)
                    elif res:
                        iteration_results.append(res)

                # -------- TRACE --------
                iteration_trace["results"] = iteration_results
                state.trace["iterations"].append(iteration_trace)

                # -------- DEDUP + USER-ORDERED MERGE --------
                existing = {_key(r): r for r in all_results}

                for r in iteration_results:
                    existing[_key(r)] = r

                all_results = sorted(
                    existing.values(),
                    key=lambda x: task_order.get(
                        (x.get("_tool"), x.get("order_id")), 999
                    ),
                )

                # -------- STOP CONDITION --------
                has_success = any(
                    isinstance(r, dict) and r.get("status") not in ["failed", None]
                    for r in iteration_results
                )

                break  # bounded single-pass

            # -------- RESPONSE --------
            structured = self.response_composer.compose(all_results, state.intent)

            # -------- RAG FALLBACK (NO TOOL RESULTS) --------
            if not all_results:
                # detect if this was a rag query
                is_rag_query = any(
                    plan.steps[0].action == "rag"
                    for _, plan in validated
                    if plan and plan.steps
                )

                if is_rag_query:
                    try:
                        rag_response = await self.rag.generate(user_query)

                        return _exit(rag_response)
                    except Exception:
                        return _exit(
                            "Unable to fetch information.", "failure", "rag_failure"
                        )

            if not all_results:
                return _exit("Unable to process request.", "failure", "empty_response")

            state.metadata["details"] = structured["details"]

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", structured["summary"])

            # -------- STORE IN CACHE --------
            cache_key = user_query.strip().lower()

            if not is_eval:
                self.cache.set(
                    cache_key,
                    {
                        "response": structured["summary"],
                        "details": structured.get("details", []),
                    },
                )

            return _exit(structured["summary"], clear_session=True)

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
        match = re.search(r"(?:ORD)?0*(\d+)", query.upper())
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
