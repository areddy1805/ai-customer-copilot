from app.llm.service import LLMService
from app.llm.models import TaskType


VALID_INTENTS = {
    "order_status",
    "refund_request",
    "refund_policy",
    "cancellation",
    "delivery_issue",
    "account_update",
    "greeting",
    "general",
}


class IntentClassifier:
    """
    Deterministic intent classifier (strict separation: transactional vs informational)
    """

    def classify(self, query: str) -> str:
        q = query.lower()

        # -------- GREETING --------
        if q in ["hi", "hello", "hey"]:
            return "greeting"

        # -------- REFUND POLICY (informational) --------
        if "refund policy" in q or "refund rules" in q:
            return "refund_policy"

        # -------- REFUND REQUEST (transactional) --------
        if "refund" in q or "money back" in q:
            return "refund_request"

        # -------- ORDER STATUS --------
        if "order" in q or "track" in q:
            return "order_status"

        # -------- CREATE TICKET --------
        if "ticket" in q:
            return "create_ticket"

        # -------- DELIVERY ISSUE --------
        if any(x in q for x in ["delayed", "late", "not delivered", "delay"]):
            return "delivery_issue"

        # -------- GENERIC ISSUE --------
        if "issue" in q or "problem" in q:
            return "delivery_issue"

        # -------- CANCELLATION --------
        if "cancel" in q:
            return "cancellation"

        # -------- ACCOUNT --------
        if any(x in q for x in ["account", "address", "update profile"]):
            return "account_update"

        # -------- DEFAULT --------
        return "general"
