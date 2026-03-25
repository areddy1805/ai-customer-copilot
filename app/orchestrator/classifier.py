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

        # -------- GREETING --------
        if q in ["hi", "hello", "hey"]:
            return "greeting"
        # -------- REFUND (highest priority) --------
        if "refund policy" in q or "policy" in q:
            return "general"

        if "refund" in q or "money back" in q:
            return "refund_request"

        # -------- TICKET / ISSUE --------
        if "ticket" in q or "issue" in q or "problem" in q:
            return "delivery_issue"

        # -------- ORDER STATUS --------
        if "order" in q:
            return "order_status"

        # -------- DELIVERY --------
        if any(x in q for x in ["delayed", "late", "not delivered", "delay"]):
            return "delivery_issue"

        # -------- CANCELLATION --------
        if "cancel" in q:
            return "cancellation"

        # -------- ACCOUNT --------
        if any(x in q for x in ["account", "address", "update profile"]):
            return "account_update"

        # -------- DEFAULT --------
        return "general"
