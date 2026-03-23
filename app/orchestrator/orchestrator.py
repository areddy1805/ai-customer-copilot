from app.orchestrator.state import ConversationState
from app.orchestrator.classifier import IntentClassifier
from app.orchestrator.router import Router
from app.llm.service import LLMService
from app.llm.models import TaskType
from app.memory.memory_service import MemoryService
from app.rag.service import RAGService


class Orchestrator:
    def __init__(self):
        self.classifier = IntentClassifier()
        self.router = Router()
        self.llm = LLMService()
        self.memory = MemoryService()
        self.rag = RAGService()

    def run(self, user_query: str, session_id: str) -> ConversationState:
        """
        Main execution pipeline
        """

        state = ConversationState(user_query=user_query)

        history = self.memory.get_messages(session_id)
        history_text = self._format_history(history) if history else ""

        intent = self.classifier.classify(user_query)
        state.intent = intent

        route = self.router.route(intent)
        state.metadata["route"] = route

        query = f"""
                Conversation History:
                {history_text}

                Current Query:
                {user_query}
                """

        if route == "direct_llm":
            response = self.llm.generate(task=TaskType.GENERAL, query=query)
            state.final_response = response

            self.memory.add_message(session_id, "user", user_query)
            self.memory.add_message(session_id, "assistant", state.final_response)

        elif route == "tool":
            state.final_response = "This request requires backend processing (tool execution not implemented yet)."

        elif route == "rag":
            response = self.rag.generate(user_query)
            state.final_response = response

        else:
            state.final_response = "Sorry, something went wrong."

        return state

    def _format_history(self, history):
        lines = []
        for msg in history:
            role = msg["role"].capitalize()
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)
