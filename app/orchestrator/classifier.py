from app.llm.service import LLMService
from app.llm.models import TaskType

VALID_INTENTS = {
    "order_status",
    "refund_request",
    "cancellation",
    "delivery_issue",
    "account_update",
    "general",
}


class IntentClassifier:
    def __init__(self):
        self.llm = LLMService()

    def classify(self, query: str) -> str:
        """
        Classifies user query into predefined intent categories
        """

        response = self.llm.generate(task=TaskType.CLASSIFICATION, query=query)

        intent = response.strip().lower()

        if intent not in VALID_INTENTS:
            return "general"

        return intent
