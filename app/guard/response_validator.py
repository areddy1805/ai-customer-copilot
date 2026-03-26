class ResponseValidator:

    def validate(self, intent: str, response: str, data: dict = None) -> bool:

        if not response:
            return False

        if not data:
            return True  # do not fail

        if intent == "order_status":
            return all(k in data for k in ["order_id", "status"])

        if intent == "refund_request":
            return all(k in data for k in ["order_id", "status"])

        if intent in ["delivery_issue", "create_ticket"]:
            return all(k in data for k in ["ticket_id", "status"])

        return True
