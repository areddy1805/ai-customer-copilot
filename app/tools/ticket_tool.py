import json
from datetime import datetime
from typing import Dict, Any
from app.tools.schemas import SupportTicketInput, ToolResponse


class TicketTool:
    def __init__(self, tickets_path: str = "data/mock_db/tickets.json"):
        self.tickets_path = tickets_path

    def _load_tickets(self):
        with open(self.tickets_path, "r") as f:
            return json.load(f)

    def create_ticket(self, input_data: Dict[str, Any]) -> ToolResponse:
        """
        Create or fetch support ticket
        """

        try:
            validated = SupportTicketInput(**input_data)

            tickets = self._load_tickets()

            order_id = input_data.get("order_id")

            if order_id:
                order_id = order_id.strip().upper()

            # Check for existing active ticket
            existing_ticket = next(
                (
                    t
                    for t in tickets
                    if t["order_id"] == order_id
                    and t["status"] in ["open", "in_progress"]
                ),
                None,
            )

            if existing_ticket:
                return ToolResponse(
                    success=True,
                    data={
                        "ticket_id": existing_ticket["ticket_id"],
                        "status": existing_ticket["status"],
                        "message": "Existing ticket found",
                    },
                )

            # Create new ticket (simulation)
            new_ticket_id = f"TICK_{datetime.now().timestamp()}"

            ticket_data = {
                "ticket_id": new_ticket_id,
                "order_id": order_id,
                "issue_type": validated.issue,
                "status": "open",
                "created_at": datetime.now().strftime("%Y-%m-%d"),
            }

            return ToolResponse(
                success=True,
                data={**ticket_data, "message": "Support ticket created successfully"},
            )

        except Exception as e:
            return ToolResponse(success=False, error=str(e))
