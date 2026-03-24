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

import re


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

    def run(self, user_query: str, session_id: str) -> ConversationState:

        state = ConversationState(user_query=user_query)

        # -------- GUARD --------
        guard_result = self.guard.evaluate(user_query, intent="unknown")

        if not guard_result["allowed"]:

            state.final_response = "Your request cannot be processed due to security or validation constraints."
            state.metadata["execution"] = "blocked"
            state.metadata["guard_reason"] = guard_result["reason"]

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", state.final_response)

            return state

        # -------- LOAD MEMORY --------
        history = self.memory.get_messages(session_id)
        history_text = self._format_history(history) if history else ""

        # -------- CLASSIFY --------
        intent = self.classifier.classify(user_query)
        state.intent = intent

        guard_result = self.guard.evaluate(user_query, intent=intent)

        # -------- FALLBACK --------
        if guard_result["action"] == "fallback":
            response = self.rag.generate(user_query)
            state.final_response = response
            state.metadata["execution"] = "rag"
            state.metadata["guard_reason"] = guard_result["reason"]

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", state.final_response)

            return state

        # -------- HUMAN ESCALATION --------

        if any(
            phrase in user_query.lower()
            for phrase in [
                "talk to human",
                "connect me to agent",
                "customer support",
                "human support",
            ]
        ):
            self._escalate(
                session_id=session_id,
                user_query=user_query,
                intent="human_request",
                reason="User requested human",
            )

            state.final_response = "Connecting you to a support agent."

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", state.final_response)

            return state

        # -------- ROUTE (COARSE) --------
        route = self.router.route(intent)
        state.metadata["route"] = route

        # -------- BUILD QUERY --------
        query = f"""
                Conversation History:
                {history_text}

                Current Query:
                {user_query}
                """

        # -------- DIRECT LLM --------
        if route == "direct_llm":
            response = self.llm.generate(task=TaskType.GENERAL, query=query)
            state.final_response = response
            state.metadata["execution"] = "direct_llm"

        # -------- RAG (EXPLICIT) --------
        elif route == "rag":
            response = self.rag.generate(user_query)
            state.final_response = response
            state.metadata["execution"] = "rag"

        # -------- TOOL (HYBRID LOGIC) --------
        elif route == "tool":

            order_id = self._extract_order_id(user_query)

            # -------- TOOL EXECUTION --------
            tool_response = None

            # ORDER STATUS
            if intent == "order_status":
                if not order_id:
                    response = self.llm.generate(
                        task=TaskType.GENERAL, query="Please provide a valid order ID."
                    )
                    state.final_response = response
                    state.metadata["execution"] = "direct_llm"
                    return state

                tool_response = self.order_tool.get_order_status({"order_id": order_id})

            # REFUND
            elif intent == "refund_request":
                tool_response = self.refund_tool.process_refund({"order_id": order_id})

            # DELIVERY / SUPPORT
            elif intent in ["delivery_issue", "account_update"]:
                tool_response = self.ticket_tool.create_ticket(
                    {"user_id": "USR1", "order_id": order_id, "issue": intent}
                )

            # -------- FORMAT TOOL RESPONSE --------
            if tool_response and tool_response.success:
                response = self.llm.generate(
                    task=TaskType.TOOL_RESPONSE,
                    query=user_query,
                    context=self._format_tool_data(tool_response.data),
                )
            else:
                # -------- ESCALATE --------
                self._escalate(
                    session_id=session_id,
                    user_query=user_query,
                    intent=intent,
                    reason="Tool failure",
                )

                response = "Your request has been escalated to a support agent."

            state.final_response = response
            state.metadata["execution"] = "tool"

        else:
            self._escalate(
                session_id=session_id,
                user_query=user_query,
                intent=intent,
                reason="Unhandled case",
            )

            state.final_response = "Your request has been escalated to support."

        # -------- SAVE MEMORY --------
        self.memory.add_message(session_id, "user", user_query)
        self.memory.add_message(session_id, "assistant", state.final_response)

        return state

    def run_stream(self, user_query: str, session_id: str):

        state = ConversationState(user_query=user_query)

        # -------- GUARD (FIRST PASS) --------
        guard_result = self.guard.evaluate(user_query, intent="unknown")

        if not guard_result["allowed"]:
            yield "Your request cannot be processed due to security or validation constraints."
            return

        # -------- HUMAN ESCALATION --------
        if any(
            phrase in user_query.lower()
            for phrase in [
                "talk to human",
                "connect me to agent",
                "customer support",
                "human support",
            ]
        ):
            self._escalate(
                session_id=session_id,
                user_query=user_query,
                intent="human_request",
                reason="User requested human",
            )

            yield "Connecting you to a support agent."
            return

        # -------- CLASSIFY --------
        intent = self.classifier.classify(user_query)
        state.intent = intent

        # -------- GUARD (SECOND PASS) --------
        guard_result = self.guard.evaluate(user_query, intent=intent)

        if guard_result["action"] == "fallback":
            # RAG streaming
            for token in self.llm.generate_stream(task=TaskType.RAG, query=user_query):
                yield token
            return

        # -------- ROUTE --------
        route = self.router.route(intent)

        # -------- DIRECT LLM --------
        if route == "direct_llm":
            for token in self.llm.generate_stream(
                task=TaskType.GENERAL, query=user_query
            ):
                yield token
            return

        # -------- TOOL --------
        elif route == "tool":

            order_id = self._extract_order_id(user_query)

            tool_response = None

            if intent == "order_status":
                if not order_id:
                    yield "Please provide a valid order ID."
                    return

                tool_response = self.order_tool.get_order_status({"order_id": order_id})

            elif intent == "refund_request":
                tool_response = self.refund_tool.process_refund({"order_id": order_id})

            elif intent in ["delivery_issue", "account_update"]:
                tool_response = self.ticket_tool.create_ticket(
                    {"user_id": "USR1", "order_id": order_id, "issue": intent}
                )

            # -------- STREAM FORMATTED RESPONSE --------
            if tool_response and tool_response.success:
                context = self._format_tool_data(tool_response.data)
            else:
                self._escalate(
                    session_id=session_id,
                    user_query=user_query,
                    intent=intent,
                    reason="Tool failure",
                )

                yield "Your request has been escalated to a support agent."
                return

            for token in self.llm.generate_stream(
                task=TaskType.TOOL_RESPONSE, query=user_query, context=context
            ):
                yield token

            return

        # -------- RAG --------
        elif route == "rag":
            for token in self.llm.generate_stream(task=TaskType.RAG, query=user_query):
                yield token
            return

        else:
            yield "Something went wrong."

    # -------- HELPERS --------

    def _format_history(self, history):
        lines = []
        for msg in history:
            role = msg["role"].capitalize()
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    def _extract_order_id(self, query: str):
        match = re.search(r"ORD\d+", query.upper())
        return match.group(0) if match else None

    def _format_tool_data(self, data: dict) -> str:
        lines = []
        for k, v in data.items():
            lines.append(f"{k}: {v}")
        return "\n".join(lines)

    def _escalate(self, session_id, user_query, intent, reason):
        self.escalation.push(
            session_id=session_id, user_query=user_query, intent=intent, reason=reason
        )
