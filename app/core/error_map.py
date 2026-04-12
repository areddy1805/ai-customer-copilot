from app.core.errors import ErrorCode


ERROR_MESSAGE_MAP = {
    ErrorCode.ORDER_NOT_FOUND: "Order {order_id} not found.",
    ErrorCode.REFUND_NOT_ALLOWED: "Refund cannot be processed until delivery is complete.",
    ErrorCode.PAYMENT_NOT_FOUND: "Payment information missing for order {order_id}.",
    ErrorCode.UNKNOWN_ERROR: "Something went wrong. Please try again.",
}


def normalize_error_code(code):
    if isinstance(code, ErrorCode):
        return code

    try:
        return ErrorCode(code)
    except Exception:
        return None


def map_error_message(error_code, data: dict):
    code = normalize_error_code(error_code)

    if not code:
        return None

    template = ERROR_MESSAGE_MAP.get(code)

    if not template:
        return None

    try:
        return template.format(**data)
    except Exception:
        return template
