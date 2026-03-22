from app.orchestrator.state import ConversationState
from app.orchestrator.classifier import IntentClassifier
from app.orchestrator.router import Router
from app.llm.service import LLMService
from app.llm.models import TaskType

class Orchestrator:
    def __init__(self):
        self.classifier = IntentClassifier()
        self.router = Router()
        self.llm = LLMService()
    
    def run(self, user_query: str)-> ConversationState:
        """
        Main execution pipeline
        """
        
        state = ConversationState(user_query=user_query)
        
        intent = self.classifier.classify(user_query)
        state.intent = intent
        
        route = self.router.route(intent)
        state.metadata["route"] = route
        
        if route == "direct_llm":
            response = self.llm.generate(
                task=TaskType.GENERAL,
                query=user_query
            )
            state.final_response = response
            
        elif route == "tool":
            state.final_response = "This request requires backend processing (tool execution not implemented yet)."

        elif route == "rag":
            state.final_response = "Knowledge retrieval not implemetned yet."
        
        else:
            state.final_response = "Sorry, something went wrong."
        
        return state