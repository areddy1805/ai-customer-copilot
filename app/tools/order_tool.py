import json
from typing import Dict, Any
from app.tools.schemas import OrderStatusInput, ToolResponse
from app.core.errors import ErrorCode


class OrderTool:
    def __init__(self, db_path: str = "data/mock_db/orders.json"):
        self.db_path = db_path

    def _load_orders(self):
        with open(self.db_path, "r") as f:
            return json.load(f)

    def get_order_status(self, input_data: Dict[str, Any]) -> ToolResponse:
        """
        Fetch order status from mock DB
        """

        try:
            validated = OrderStatusInput(**input_data)

            orders = self._load_orders()

            for order in orders:
                if order["order_id"] == validated.order_id:
                    return ToolResponse(success=True, data=order)

            return ToolResponse(
                success=False,
                error="Order not found",
                error_code=ErrorCode.ORDER_NOT_FOUND,
            )

        except Exception as e:
            return ToolResponse(
                success=False, error=str(e), error_code=ErrorCode.UNKNOWN_ERROR
            )
