class ErrorMapper:

    ERROR_MAP = {
        "Order not found": ("business_error", "ORDER_NOT_FOUND"),
        "Refund not allowed: Order not delivered": (
            "business_error",
            "REFUND_NOT_DELIVERED",
        ),
        "Payment record not found": ("tool_error", "PAYMENT_NOT_FOUND"),
    }

    @classmethod
    def map(cls, error_msg: str):
        for key in cls.ERROR_MAP:
            if key.lower() in error_msg.lower():
                etype, ecode = cls.ERROR_MAP[key]
                return {
                    "error_type": etype,
                    "error_code": ecode,
                }

        return {
            "error_type": "system_error",
            "error_code": "UNKNOWN_ERROR",
        }
