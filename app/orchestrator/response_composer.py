class ResponseComposer:

    def compose(self, results: list, intent: str) -> dict:
        summaries = []
        details = []

        for data in results:
            if not data:
                continue

            tool = data.get("_tool")

            # -------- ORDER --------
            if tool == "order":
                text = f"Order {data.get('order_id')} is {data.get('status')}."
                summaries.append(text)
                details.append({"type": "order", "data": data})

            # -------- REFUND --------
            elif tool == "refund":
                text = f"Refund for {data.get('order_id')} is {data.get('status')}."
                summaries.append(text)
                details.append({"type": "refund", "data": data})

            # -------- TICKET --------
            elif tool == "ticket":
                text = f"Ticket {data.get('ticket_id')} is {data.get('status')}."
                summaries.append(text)
                details.append({"type": "ticket", "data": data})

            # -------- RAG --------
            elif tool == "rag":
                if data.get("response"):
                    summaries.append(data["response"])
                    details.append({"type": "rag", "data": data["response"]})

            # -------- FALLBACK --------
            elif "response" in data:
                summaries.append(data["response"])
                details.append({"type": "rag", "data": data["response"]})

        # -------- FINAL SUMMARY --------
        summary = "\n".join(summaries) if summaries else "Unable to process request."

        return {
            "summary": summary,
            "details": details,
        }
