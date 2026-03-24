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

    def run(self, user_query: str, session_id: str) -> ConversationState:
        start_time = time.time()
        state = ConversationState(user_query=user_query)
        intent = None
        route = None

        try:
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

            # -------- HUMAN ESCALATION --------
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

            # -------- CLASSIFICATION --------
            t0 = time.time()
            intent = self.classifier.classify(user_query)
            t1 = time.time()

            state.intent = intent
            state.metadata["latency_classification_ms"] = int((t1 - t0) * 1000)

            # -------- CACHE (GLOBAL FOR NON-TOOL) --------
            cached = self.cache.get(user_query)
            if cached:
                state.final_response = cached
                state.metadata["execution"] = "cache"

                self._log(
                    session_id,
                    user_query,
                    intent,
                    None,
                    "cache",
                    start_time,
                    state.metadata,
                )
                return state

            # -------- GUARD (SECOND PASS) --------
            guard = self.guard.evaluate(user_query, intent)

            if guard["action"] == "fallback":
                t0 = time.time()
                response = self.rag.generate(user_query)
                t1 = time.time()

                state.metadata["latency_rag_ms"] = int((t1 - t0) * 1000)
                state.metadata["execution"] = "rag"
                state.final_response = response

                self.cache.set(user_query, response)

                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", response)

                self._log(
                    session_id,
                    user_query,
                    intent,
                    None,
                    "rag",
                    start_time,
                    state.metadata,
                )
                return state

            # -------- ROUTE --------
            route = self.router.route(intent)
            state.metadata["route"] = route

            # -------- MEMORY --------
            history = self.memory.get_messages(session_id)
            history_text = self._format_history(history) if history else ""

            query = f"""
Conversation History:
{history_text}

Current Query:
{user_query}
"""

            # -------- DIRECT LLM --------
            if route == "direct_llm":
                t0 = time.time()
                response = self.llm.generate(TaskType.GENERAL, query)
                t1 = time.time()

                state.metadata["latency_llm_ms"] = int((t1 - t0) * 1000)
                state.metadata["execution"] = "direct_llm"
                state.final_response = response

                self.cache.set(user_query, response)

            # -------- RAG --------
            elif route == "rag":
                t0 = time.time()
                response = self.rag.generate(user_query)
                t1 = time.time()

                state.metadata["latency_rag_ms"] = int((t1 - t0) * 1000)
                state.metadata["execution"] = "rag"
                state.final_response = response

                self.cache.set(user_query, response)

            # -------- TOOL --------
            elif route == "tool":
                order_id = self._extract_order_id(user_query)
                tool_response = None

                t0 = time.time()

                if intent == "order_status":
                    if not order_id:
                        state.final_response = "Please provide a valid order ID."
                        state.metadata["execution"] = "direct_llm"
                        self._log(
                            session_id,
                            user_query,
                            intent,
                            route,
                            "direct_llm",
                            start_time,
                            state.metadata,
                        )
                        return state

                    tool_response = self.order_tool.get_order_status(
                        {"order_id": order_id}
                    )

                elif intent == "refund_request":
                    tool_response = self.refund_tool.process_refund(
                        {"order_id": order_id}
                    )

                else:
                    tool_response = self.ticket_tool.create_ticket(
                        {"user_id": "USR1", "order_id": order_id, "issue": intent}
                    )

                t1 = time.time()
                state.metadata["latency_tool_ms"] = int((t1 - t0) * 1000)

                if tool_response and tool_response.success:
                    response = self._format_tool_response(tool_response.data, intent)

                    state.metadata["execution"] = "tool"
                    state.final_response = response

                else:
                    self._escalate(session_id, user_query, intent, "Tool failure")
                    state.metadata["execution"] = "escalated"
                    state.final_response = (
                        "Your request has been escalated to a support agent."
                    )

            else:
                self._escalate(session_id, user_query, intent, "Unhandled case")
                state.metadata["execution"] = "escalated"
                state.final_response = "Your request has been escalated to support."

            # -------- SAVE MEMORY --------
            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", state.final_response)

            self._log(
                session_id,
                user_query,
                intent,
                state.metadata.get("route"),
                state.metadata.get("execution"),
                start_time,
                state.metadata,
            )

            return state

        except Exception as e:
            try:
                self._escalate(session_id, user_query, intent or "unknown", str(e))
            except:
                pass

            state.metadata["execution"] = "system_failure"
            state.final_response = (
                "Something went wrong. Your request has been escalated."
            )

            self._log(
                session_id,
                user_query,
                intent,
                None,
                "system_failure",
                start_time,
                state.metadata,
            )
            return state

    # -------- LOGGER --------
    def _log(self, session_id, query, intent, route, execution, start_time, metadata):
        try:
            latency = int((time.time() - start_time) * 1000)

            status = "success"
            if execution in ["escalated", "system_failure"]:
                status = "failure"

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

    # -------- HELPERS --------
    def _extract_order_id(self, query: str):
        match = re.search(r"ORD\d+", query.upper())
        return match.group(0) if match else None

    def _format_history(self, history):
        return "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in history)

    def _format_tool_response(self, data: dict, intent: str) -> str:

        if intent == "order_status":
            return f"Your order {data.get('order_id')} is {data.get('status')} and expected by {data.get('delivery_eta')}."

        if intent == "refund_request":
            return f"Refund status for order {data.get('order_id')} is {data.get('status')}."

        if intent in ["delivery_issue", "account_update"]:
            return f"Ticket {data.get('ticket_id')} is currently {data.get('status')}."

        return "Request processed successfully."

    def _escalate(self, session_id, user_query, intent, reason):
        self.escalation.push(
            session_id=session_id,
            user_query=user_query,
            intent=intent,
            reason=reason,
        )
