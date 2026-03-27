import json
from typing import Dict, Any
from app.tools.schemas import RefundRequestInput, ToolResponse


class RefundTool:
    def __init__(
        self,
        orders_path: str = "data/mock_db/orders.json",
        payments_path: str = "data/mock_db/payments.json",
        refunds_path: str = "data/mock_db/refunds.json",
    ):
        self.orders_path = orders_path
        self.payments_path = payments_path
        self.refunds_path = refunds_path

    def _load_json(self, path: str):
        with open(path, "r") as f:
            return json.load(f)

    def process_refund(self, input_data: Dict[str, Any]) -> ToolResponse:
        """
        Process refund using real data relationships:
        orders + payments + refunds
        """
        try:
            validated = RefundRequestInput(**input_data)

            orders = self._load_json(self.orders_path)
            payments = self._load_json(self.payments_path)
            refunds = self._load_json(self.refunds_path)

            order = next(
                (o for o in orders if o["order_id"] == validated.order_id), None
            )

            if not order:
                return ToolResponse(success=False, error="Order not found")

            # -------- EXISTING REFUND (FIX) --------
            existing_refund = next(
                (r for r in refunds if r["order_id"] == validated.order_id), None
            )

            if existing_refund:
                return ToolResponse(
                    success=True,
                    data={
                        "order_id": validated.order_id,
                        "status": existing_refund["status"],
                        "amount": existing_refund["amount"],
                        "mode": existing_refund["mode"],
                        "_type": "refund",
                    },
                )

            # -------- VALIDATION --------
            if order["status"] != "delivered":
                return ToolResponse(
                    success=False,
                    error="Refund not allowed: Order not delivered",
                )

            payment = next(
                (p for p in payments if p["order_id"] == validated.order_id), None
            )

            if not payment:
                return ToolResponse(success=False, error="Payment record not found")

            # -------- REFUND MODE --------
            refund_mode = (
                "original_method" if payment["method"] == "prepaid" else "wallet"
            )

            # -------- CREATE REFUND --------
            refund_data = {
                "order_id": validated.order_id,
                "status": "initiated",
                "amount": order["amount"],
                "mode": refund_mode,
            }

            return ToolResponse(success=True, data=refund_data)

        except Exception as e:
            return ToolResponse(success=False, error=str(e))
