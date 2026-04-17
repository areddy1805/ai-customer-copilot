import json
from typing import Dict, Any
from app.tools.schemas import OrderStatusInput, ToolResponse


class OrderTool:
    def __init__(self, db_path: str = "data/mock_db/orders.json"):
        self.db_path = db_path

    def _load_orders(self):
        with open(self.db_path, "r") as f:
            return json.load(f)

    def get_order_status(self, input_data: Dict[str, Any]) -> ToolResponse:
        try:
            validated = OrderStatusInput(**input_data)

            # -------- NORMALIZATION --------
            raw_id = validated.order_id.strip().upper()

            import re

            match = re.search(r"ORD0*(\d+)", raw_id)

            if not match:
                return ToolResponse(
                    success=True,
                    data={
                        "order_id": raw_id,
                        "status": "failed",
                        "reason": "Invalid order_id format",
                    },
                )

            order_id = f"ORD{int(match.group(1))}"

            orders = self._load_orders()

            order = next(
                (o for o in orders if o["order_id"] == order_id),
                None,
            )

            # -------- NOT FOUND --------
            if not order:
                return ToolResponse(
                    success=True,
                    data={
                        "order_id": order_id,
                        "status": "failed",
                        "reason": "Order not found",
                    },
                )

            # -------- SUCCESS --------
            return ToolResponse(
                success=True,
                data={
                    "order_id": order.get("order_id"),
                    "status": order.get("status"),
                },
            )

        except Exception as e:
            return ToolResponse(
                success=True,
                data={
                    "order_id": input_data.get("order_id"),
                    "status": "failed",
                    "reason": str(e),
                },
            )
