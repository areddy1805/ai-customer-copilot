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
    """
    Deterministic intent classifier
    """

    def classify(self, query: str) -> str:
        q = query.lower()

        # -------- ORDER STATUS --------
        if "order" in q and any(x in q for x in ["where", "status", "track"]):
            return "order_status"

        # -------- REFUND --------
        if "refund" in q or "money back" in q:
            return "refund_request"

        # -------- CANCELLATION --------
        if "cancel" in q:
            return "cancellation"

        # -------- DELIVERY --------
        if any(x in q for x in ["delayed", "late", "not delivered", "delay"]):
            return "delivery_issue"

        # -------- ACCOUNT --------
        if any(x in q for x in ["account", "address", "update profile"]):
            return "account_update"

        # -------- DEFAULT --------
        return "general"
