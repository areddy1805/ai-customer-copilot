class ResponseComposer:

    def compose(self, results: list, intent: str) -> dict:
        summary = None
        details = []

        for data in results:
            tool = data.get("_tool")

            if tool == "order":
                summary = f"Order {data.get('order_id')} is {data.get('status')}."
                details.append({"type": "order", "data": data})

            elif tool == "refund":
                summary = f"Refund for {data.get('order_id')} is {data.get('status')}."
                details.append({"type": "refund", "data": data})

            elif tool == "ticket":
                summary = f"Ticket {data.get('ticket_id')} is {data.get('status')}."
                details.append({"type": "ticket", "data": data})

            elif tool == "rag":
                if data.get("response"):
                    details.append({"type": "rag", "data": data["response"]})

            elif "response" in data:
                details.append({"type": "rag", "data": data["response"]})

        if not summary and details:
            summary = details[0]["data"]

        return {
            "summary": summary or "Unable to process request.",
            "details": details,
        }
