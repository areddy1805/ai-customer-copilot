class Executor:

    def __init__(self, tools):
        self.tools = tools

    def execute(self, plan):

        context = {}
        query = getattr(plan, "query", "")

        for step in plan.steps:
            action = step.action

            # -------- GET ORDER --------
            if action in ["get_order", "order_status"]:
                order_id = self.tools["extract_order_id"](
                    step.input.get("query", query)
                )
                res = self.tools["order"].get_order_status({"order_id": order_id})

                if not res or not res.success:
                    return res

                # single-step plan → return immediately
                if len(plan.steps) == 1:
                    return res

                context["order"] = res.data
                continue

            # -------- CHECK REFUND ELIGIBILITY --------
            elif action == "check_refund_eligibility":
                order = context.get("order")
                if not order:
                    return {"type": "rag", "query": query}
                continue

            # -------- PROCESS REFUND --------
            elif action in ["process_refund", "refund_request"]:
                order_id = context.get("order", {}).get("order_id") or self.tools[
                    "extract_order_id"
                ](step.input.get("query", query))

                res = self.tools["refund"].process_refund({"order_id": order_id})
                return res

            # -------- CHECK TICKET --------
            elif action == "check_ticket":
                continue

            # -------- CREATE / FETCH TICKET --------
            elif action in ["create_or_fetch_ticket", "create_ticket"]:
                order_id = context.get("order", {}).get("order_id") or self.tools[
                    "extract_order_id"
                ](step.input.get("query", query))

                res = self.tools["ticket"].create_ticket(
                    {
                        "user_id": "USR1",
                        "order_id": order_id,
                        "issue": "delivery_issue",
                    }
                )
                return res

            # -------- RAG --------
            elif action in ["fallback_rag", "rag"]:
                return {"type": "rag", "query": step.input.get("query", query)}

        # -------- FINAL FALLBACK --------
        return {"type": "rag", "query": query}
