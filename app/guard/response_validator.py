class ResponseValidator:

    def validate(self, intent: str, response: str, data: dict = None) -> bool:

        if not response or not response.strip():
            return False

        # -------- ORDER --------
        if intent == "order_status":
            required = ["order_id", "status", "delivery_eta"]
            return self._contains_all(response, data, required)

        # -------- REFUND --------
        if intent == "refund_request":
            required = ["order_id", "status"]
            return self._contains_all(response, data, required)

        # -------- TICKET --------
        if intent in ["delivery_issue", "account_update"]:
            required = ["ticket_id", "status"]
            return self._contains_all(response, data, required)

        return True

    def _contains_all(self, response: str, data: dict, fields: list):

        if not data:
            return False

        for f in fields:
            val = data.get(f)
            if val is None:
                return False

            if str(val) not in response:
                return False

        return True
