from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.core.errors import ErrorCode


# ---------------------------
# Base Output Schema
# ---------------------------


class ToolResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[ErrorCode] = None


# ---------------------------
# Order Tool Input
# ---------------------------


class OrderStatusInput(BaseModel):
    order_id: str = Field(..., min_length=3)


# ---------------------------
# Refund Tool Input
# ---------------------------


class RefundRequestInput(BaseModel):
    order_id: str
    reason: Optional[str] = None


# ---------------------------
# Ticket Tool Input
# ---------------------------


class SupportTicketInput(BaseModel):
    user_id: str
    issue: str
