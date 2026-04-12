import re


class TaskDecomposer:

    def decompose(self, query: str):
        parts = [p.strip() for p in query.lower().split("and") if p.strip()]

        tasks = []

        for part in parts:
            order_ids = re.findall(r"ord\d+", part)

            for oid in order_ids:

                if "refund" in part:
                    tasks.append({"intent": "refund_request", "order_id": oid.upper()})

                elif "track" in part or "order" in part:
                    tasks.append({"intent": "order_status", "order_id": oid.upper()})

                elif "ticket" in part or "issue" in part:
                    tasks.append({"intent": "create_ticket", "order_id": oid.upper()})

        return tasks
