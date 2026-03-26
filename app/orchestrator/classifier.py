import re


class IntentClassifier:
    def __init__(self):
        pass

    def classify(self, query: str) -> str:
        q = query.lower()

        # -------- RULE BASED (PRIMARY) --------
        if self._is_order_status(q):
            return "order_status"

        if self._is_policy(q):
            return "refund_policy"

        if self._is_refund(q):
            return "refund_request"

        if self._is_delivery_issue(q):
            return "delivery_issue"

        if self._is_ticket(q):
            return "create_ticket"

        # -------- FALLBACK --------
        return "general"

    # ---------------- RULES ----------------

    def _is_order_status(self, q):
        return any(
            k in q for k in ["where is my order", "track", "order status", "order?"]
        )

    def _is_refund(self, q):
        return any(k in q for k in ["refund", "money back", "return"])

    def _is_delivery_issue(self, q):
        return any(
            k in q
            for k in [
                "not delivered",
                "didn’t get",
                "did not get",
                "not received",
                "missing package",
            ]
        )

    def _is_ticket(self, q):
        return any(k in q for k in ["create ticket", "complaint", "issue", "problem"])

    def _is_policy(self, q):
        return "policy" in q
