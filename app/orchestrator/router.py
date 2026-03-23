from typing import Literal

Route = Literal["tool", "rag", "direct_llm"]


class Router:
    """
    Determines execution path based on intent
    """

    def route(self, intent: str) -> Route:
        """
        Returns execution path based on intent
        """

        if intent == "order_status":
            return "tool"

        elif intent == "refund_request":
            return "tool"

        elif intent == "cancellation":
            return "tool"

        elif intent == "delivery_issue":
            return "tool"

        elif intent == "account_update":
            return "tool"

        elif intent == "general":
            return "direct_llm"

        return "direct_llm"
