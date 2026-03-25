from app.orchestrator.plan import Plan, Step


class Planner:

    def create_plan(self, intent: str, query: str):

        if "ticket" in query.lower():
            return Plan(
                [
                    Step("get_order", {"query": query}),
                    Step("create_or_fetch_ticket", {}),
                ],
                query=query,
            )

        if intent == "refund_request":
            return Plan(
                [
                    Step("get_order", {"query": query}),
                    Step("check_refund_eligibility", {}),
                    Step("process_refund", {}),
                ],
                query=query,
            )

        if intent == "order_status":
            return Plan([Step("get_order", {"query": query})], query=query)

        if intent == "delivery_issue":
            return Plan(
                [
                    Step("get_order", {"query": query}),
                    Step("check_ticket", {}),
                    Step("create_or_fetch_ticket", {}),
                ],
                query=query,
            )

        return Plan([Step("fallback_rag", {"query": query})], query=query)
