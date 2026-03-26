class Router:
    def route(self, intent: str) -> str:
        if intent == "refund_policy":
            return "rag"
        return "tool"
