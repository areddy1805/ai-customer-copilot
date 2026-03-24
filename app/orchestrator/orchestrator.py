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

    def run(self, user_query: str, session_id: str) -> ConversationState:
        start_time = time.time()
        state = ConversationState(user_query=user_query)
        intent = None

        try:
            # -------- GUARD --------
            guard_result = self.guard.evaluate(user_query, intent="unknown")

            if not guard_result["allowed"]:
                state.final_response = "Your request cannot be processed due to security or validation constraints."
                state.metadata["execution"] = "blocked"

                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", state.final_response)

                self._log(
                    session_id, user_query, None, None, "blocked", start_time, "blocked"
                )
                return state

            # -------- HUMAN ESCALATION (EARLY OVERRIDE) --------
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
                    "escalated",
                )
                return state

            # -------- LOAD MEMORY --------
            history = self.memory.get_messages(session_id)
            history_text = self._format_history(history) if history else ""

            # -------- CLASSIFY --------
            intent = self.classifier.classify(user_query)
            state.intent = intent

            # -------- GUARD (SECOND PASS) --------
            guard_result = self.guard.evaluate(user_query, intent=intent)

            # -------- FALLBACK --------
            if guard_result["action"] == "fallback":
                response = self.rag.generate(user_query)

                state.final_response = response
                state.metadata["execution"] = "rag"

                self.memory.add_message(session_id, "user", user_query)
                self.memory.add_message(session_id, "assistant", response)

                self._log(
                    session_id, user_query, intent, None, "rag", start_time, "success"
                )
                return state

            # -------- ROUTE --------
            route = self.router.route(intent)
            state.metadata["route"] = route

            query = f"""
                    Conversation History:
                    {history_text}

                    Current Query:
                    {user_query}
                    """

            # -------- DIRECT LLM --------
            if route == "direct_llm":
                response = self.llm.generate(TaskType.GENERAL, query)
                state.final_response = response
                state.metadata["execution"] = "direct_llm"

            # -------- RAG --------
            elif route == "rag":
                response = self.rag.generate(user_query)
                state.final_response = response
                state.metadata["execution"] = "rag"

            # -------- TOOL --------
            elif route == "tool":
                order_id = self._extract_order_id(user_query)
                tool_response = None

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
                            "success",
                        )
                        return state

                    tool_response = self.order_tool.get_order_status(
                        {"order_id": order_id}
                    )

                elif intent == "refund_request":
                    tool_response = self.refund_tool.process_refund(
                        {"order_id": order_id}
                    )

                elif intent in ["delivery_issue", "account_update"]:
                    tool_response = self.ticket_tool.create_ticket(
                        {"user_id": "USR1", "order_id": order_id, "issue": intent}
                    )

                if tool_response and tool_response.success:
                    response = self.llm.generate(
                        TaskType.TOOL_RESPONSE,
                        user_query,
                        self._format_tool_data(tool_response.data),
                    )
                    state.final_response = response
                    state.metadata["execution"] = "tool"

                else:
                    self._escalate(session_id, user_query, intent, "Tool failure")
                    state.final_response = (
                        "Your request has been escalated to a support agent."
                    )
                    state.metadata["execution"] = "escalated"

            else:
                self._escalate(session_id, user_query, intent, "Unhandled case")
                state.final_response = "Your request has been escalated to support."
                state.metadata["execution"] = "escalated"

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
                "success",
            )

            return state

        except Exception as e:
            try:
                self._escalate(session_id, user_query, intent or "unknown", str(e))
            except:
                pass

            state.final_response = (
                "Something went wrong. Your request has been escalated."
            )
            state.metadata["execution"] = "system_failure"

            self._log(
                session_id,
                user_query,
                intent,
                None,
                "system_failure",
                start_time,
                "failure",
            )
            return state

    def run_stream(self, user_query: str, session_id: str):
        try:
            guard = self.guard.evaluate(user_query, "unknown")

            if not guard["allowed"]:
                yield "Your request cannot be processed due to security or validation constraints."
                return

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
                yield "Connecting you to a support agent."
                return

            intent = self.classifier.classify(user_query)

            guard = self.guard.evaluate(user_query, intent)

            if guard["action"] == "fallback":
                for t in self.llm.generate_stream(TaskType.RAG, user_query):
                    yield t
                return

            route = self.router.route(intent)

            if route == "direct_llm":
                for t in self.llm.generate_stream(TaskType.GENERAL, user_query):
                    yield t
                return

            elif route == "tool":
                order_id = self._extract_order_id(user_query)

                if intent == "order_status" and not order_id:
                    yield "Please provide a valid order ID."
                    return

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
                    yield "Your request has been escalated to a support agent."
                    return

                context = self._format_tool_data(res.data)

                for t in self.llm.generate_stream(
                    TaskType.TOOL_RESPONSE, user_query, context
                ):
                    yield t
                return

            elif route == "rag":
                for t in self.llm.generate_stream(TaskType.RAG, user_query):
                    yield t
                return

            yield "Something went wrong."

        except Exception:
            yield "Something went wrong. Your request has been escalated."

    # -------- HELPERS --------

    def _log(self, session_id, query, intent, route, execution, start_time, status):
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
            )
        except:
            pass

    def _extract_order_id(self, query: str):
        match = re.search(r"ORD\d+", query.upper())
        return match.group(0) if match else None

    def _format_history(self, history):
        return "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in history)

    def _format_tool_data(self, data: dict) -> str:
        return "\n".join(f"{k}: {v}" for k, v in data.items())

    def _escalate(self, session_id, user_query, intent, reason):
        self.escalation.push(
            session_id=session_id,
            user_query=user_query,
            intent=intent,
            reason=reason,
        )
