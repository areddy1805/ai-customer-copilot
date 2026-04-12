import json
from typing import Dict, Any
from app.tools.schemas import RefundRequestInput, ToolResponse
from app.core.errors import ErrorCode


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
        try:
            validated = RefundRequestInput(**input_data)

            orders = self._load_json(self.orders_path)
            payments = self._load_json(self.payments_path)
            refunds = self._load_json(self.refunds_path)

            order = next(
                (o for o in orders if o["order_id"] == validated.order_id), None
            )

            if not order:
                return ToolResponse(
                    success=False,
                    error="Order not found",
                    data={"order_id": validated.order_id},
                    error_code=ErrorCode.ORDER_NOT_FOUND,
                )

            # -------- EXISTING REFUND --------
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
                    },
                )

            # -------- VALIDATION --------
            if order["status"] != "delivered":
                return ToolResponse(
                    success=False,
                    error="Refund not allowed: Order not delivered",
                    data={"order_id": validated.order_id},
                    error_code=ErrorCode.REFUND_NOT_ALLOWED,
                )

            payment = next(
                (p for p in payments if p["order_id"] == validated.order_id), None
            )

            if not payment:
                return ToolResponse(
                    success=False,
                    error="Payment record not found",
                    data={"order_id": validated.order_id},
                    error_code=ErrorCode.PAYMENT_NOT_FOUND,
                )

            # -------- REFUND MODE --------
            refund_mode = (
                "original_method" if payment["method"] == "prepaid" else "wallet"
            )

            refund_data = {
                "order_id": validated.order_id,
                "status": "initiated",
                "amount": order["amount"],
                "mode": refund_mode,
            }

            # -------- OPTIONAL: PERSIST --------
            refunds.append(refund_data)
            self._save_json(self.refunds_path, refunds)

            return ToolResponse(
                success=True,
                data={
                    "order_id": validated.order_id,
                    "status": "initiated",
                    "amount": order["amount"],
                    "mode": refund_mode,
                },
            )

        except Exception as e:
            return ToolResponse(
                success=False,
                error=str(e),
                data={"order_id": input_data.get("order_id")},
                error_code=ErrorCode.UNKNOWN_ERROR,
            )
