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
            route = self.router.route(intent)
            state.metadata["route"] = route

            cache_key = f"{intent}:{self._normalize(user_query)}"

            # -------- CACHE --------
            if route != "tool":

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

            if guard["action"] == "fallback" or route == "rag":

                if not self.rag_cb.allow():
                    self.metrics.inc("circuit_open")
                    state.final_response = (
                        "Service temporarily unavailable. Please try again later."
                    )
                    self.inflight.delete(key)
                    return state

                try:
                    response = retry(lambda: self.rag.generate(user_query))
                    self.rag_cb.record_success()
                except Exception:
                    self.rag_cb.record_failure()
                    self.inflight.delete(key)
                    raise

                state.final_response = response
                self.cache.set(cache_key, response)
                self.inflight.set(key, response)
                if (
                    response
                    and len(response) > 20
                    and "escalated" not in response.lower()
                    and "something went wrong" not in response.lower()
                ):
                    self.semantic_cache.set(user_query, response)
                self.metrics.inc("requests_success")
                return state

            # -------- CONCURRENCY --------
            if route in ["rag", "direct_llm"]:
                if not self.concurrent.acquire():
                    state.final_response = "System is busy. Please try again shortly."
                    self.inflight.delete(key)
                    return state
                acquired = True

            # -------- DIRECT LLM --------
            if route == "direct_llm":

                if not self.llm_cb.allow():
                    self.metrics.inc("circuit_open")
                    state.final_response = (
                        "Service temporarily unavailable. Please try again later."
                    )
                    self.inflight.delete(key)
                    return state

                try:
                    response = retry(
                        lambda: self.llm.generate(TaskType.GENERAL, user_query)
                    )
                    self.llm_cb.record_success()
                except Exception:
                    self.llm_cb.record_failure()
                    self.inflight.delete(key)
                    raise

                if not self.validator.validate(intent, response):
                    response = "Unable to process your request accurately."
                    self.metrics.inc("validation_failures")

                state.final_response = response
                self.cache.set(cache_key, response)
                self.inflight.set(key, response)
                if (
                    response
                    and len(response) > 20
                    and "escalated" not in response.lower()
                    and "something went wrong" not in response.lower()
                ):
                    self.semantic_cache.set(user_query, response)
                self.metrics.inc("requests_success")

            # -------- TOOL --------
            elif route == "tool":

                order_id = self._extract_order_id(user_query)

                if intent == "order_status":
                    res = self.order_tool.get_order_status({"order_id": order_id})
                elif intent == "refund_request":
                    res = self.refund_tool.process_refund({"order_id": order_id})
                else:
                    res = self.ticket_tool.create_ticket(
                        {"user_id": "USR1", "order_id": order_id, "issue": intent}
                    )

                if not res or not res.success:
                    self._escalate(session_id, user_query, intent, "Tool failure")
                    response = "Your request has been escalated to a support agent."
                    state.final_response = response
                    state.metadata["execution"] = "escalated"
                    self.metrics.inc("requests_failure")
                    self.metrics.inc("requests_escalated")
                    self.inflight.set(key, response)
                    return state

                if intent == "order_status":
                    response = f"Your order {res.data.get('order_id')} is {res.data.get('status')} and expected by {res.data.get('delivery_eta')}."
                elif intent == "refund_request":
                    response = f"Refund status for order {res.data.get('order_id')} is {res.data.get('status')}."
                else:
                    response = f"Ticket {res.data.get('ticket_id')} is currently {res.data.get('status')}."

                if not self.validator.validate(intent, response, res.data):
                    self._escalate(
                        session_id, user_query, intent, "Response validation failed"
                    )

                    response = "Your request has been escalated to a support agent."
                    state.metadata["execution"] = "validation_failed"

                    self.metrics.inc("requests_failure")
                    self.metrics.inc("requests_escalated")

                state.final_response = response
                self.inflight.set(key, response)
                if (
                    response
                    and len(response) > 20
                    and "escalated" not in response.lower()
                    and "something went wrong" not in response.lower()
                ):
                    self.semantic_cache.set(user_query, response)
                self.metrics.inc("requests_success")

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", state.final_response)

            # -------- LATENCY --------
            latency = int((time.time() - start_time) * 1000)
            self.metrics.observe("total_latency", latency)

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

            route = self.router.route(intent)

            cache_key = f"{intent}:{self._normalize(user_query)}"

            if route != "tool":

                # -------- SEMANTIC CACHE --------
                cached = self.semantic_cache.get(user_query)
                if cached:
                    self.metrics.inc("semantic_cache_hits")
                    self.inflight.set(key, cached)
                    yield cached
                    return
                else:
                    self.metrics.inc("semantic_cache_misses")

                # -------- EXACT CACHE --------
                cached = self.cache.get(cache_key)
                if cached:
                    self.metrics.inc("cache_hits")
                    self.inflight.set(key, cached)
                    yield cached
                    return
                else:
                    self.metrics.inc("cache_misses")

            if route in ["rag", "direct_llm"]:
                if not self.concurrent.acquire():
                    self.inflight.delete(key)
                    yield "System is busy. Please try again shortly."
                    return
                acquired = True

            guard = self.guard.evaluate(user_query, intent)

            # -------- RAG --------
            if guard["action"] == "fallback" or route == "rag":

                if not self.rag_cb_stream.allow():
                    self.metrics.inc("circuit_open")
                    self.inflight.delete(key)
                    yield "Service temporarily unavailable. Please try again later."
                    return

                try:
                    tokens = retry(
                        lambda: list(self.llm.generate_stream(TaskType.RAG, user_query))
                    )
                    for t in tokens:
                        final_response += t
                        yield t
                    self.rag_cb_stream.record_success()
                except Exception:
                    self.rag_cb_stream.record_failure()
                    self.inflight.delete(key)
                    raise

                self.inflight.set(key, final_response)
                self.cache.set(cache_key, final_response)

                if (
                    final_response
                    and len(final_response) > 20
                    and "escalated" not in final_response.lower()
                    and "something went wrong" not in final_response.lower()
                ):
                    self.semantic_cache.set(user_query, final_response)

                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", final_response)
                return

            # -------- DIRECT LLM --------
            if route == "direct_llm":

                if not self.llm_cb_stream.allow():
                    self.metrics.inc("circuit_open")
                    self.inflight.delete(key)
                    yield "Service temporarily unavailable. Please try again later."
                    return

                try:
                    tokens = retry(
                        lambda: list(
                            self.llm.generate_stream(TaskType.GENERAL, user_query)
                        )
                    )
                    for t in tokens:
                        final_response += t
                        yield t
                    self.llm_cb_stream.record_success()
                except Exception:
                    self.llm_cb_stream.record_failure()
                    self.inflight.delete(key)
                    raise

                self.inflight.set(key, final_response)
                self.cache.set(cache_key, final_response)

                if (
                    final_response
                    and len(final_response) > 20
                    and "escalated" not in final_response.lower()
                    and "something went wrong" not in final_response.lower()
                ):
                    self.semantic_cache.set(user_query, final_response)

                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", final_response)
                return

            # -------- TOOL --------
            if route == "tool":

                order_id = self._extract_order_id(user_query)

                if intent == "order_status":
                    res = self.order_tool.get_order_status({"order_id": order_id})
                elif intent == "refund_request":
                    res = self.refund_tool.process_refund({"order_id": order_id})
                else:
                    res = self.ticket_tool.create_ticket(
                        {"user_id": "USR1", "order_id": order_id, "issue": intent}
                    )

                if not res or not res.success:
                    self._escalate(session_id, user_query, intent, "Tool failure")
                    final_response = (
                        "Your request has been escalated to a support agent."
                    )
                    self.metrics.inc("requests_failure")
                    self.metrics.inc("requests_escalated")
                    self.inflight.set(key, final_response)
                    yield final_response
                    return

                if intent == "order_status":
                    final_response = f"Your order {res.data.get('order_id')} is {res.data.get('status')} and expected by {res.data.get('delivery_eta')}."
                elif intent == "refund_request":
                    final_response = f"Refund status for order {res.data.get('order_id')} is {res.data.get('status')}."
                else:
                    final_response = f"Ticket {res.data.get('ticket_id')} is currently {res.data.get('status')}."

                if not self.validator.validate(intent, final_response, res.data):
                    self._escalate(
                        session_id, user_query, intent, "Response validation failed"
                    )

                    final_response = (
                        "Your request has been escalated to a support agent."
                    )

                    self.inflight.set(key, final_response)
                    self.metrics.inc("validation_failures")
                    yield final_response
                    return

                self.metrics.inc("requests_success")
                self.inflight.set(key, final_response)

                if (
                    final_response
                    and len(final_response) > 20
                    and "escalated" not in final_response.lower()
                    and "something went wrong" not in final_response.lower()
                ):
                    self.semantic_cache.set(user_query, final_response)

                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", final_response)

                yield final_response
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
