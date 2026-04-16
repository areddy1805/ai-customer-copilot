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

            orders = self._load_orders()

            order = next(
                (o for o in orders if o["order_id"] == validated.order_id), None
            )

            # -------- NOT FOUND → BUSINESS FAILURE (NOT SYSTEM FAILURE) --------
            if not order:
                return ToolResponse(
                    success=True,
                    data={
                        "order_id": validated.order_id,
                        "status": "failed",
                        "reason": "Order not found",
                    },
                )

            # -------- SUCCESS (NORMALIZED SHAPE) --------
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
