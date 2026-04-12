from app.orchestrator.orchestrator import Orchestrator
from app.orchestrator.executor import Executor
from app.orchestrator.tool_registry import ToolRegistry

from app.tools.order_tool import OrderTool
from app.tools.refund_tool import RefundTool
from app.tools.ticket_tool import TicketTool


# ---- TOOL REGISTRY ----
tool_registry = ToolRegistry()

tool_registry.register("get_order", OrderTool())
tool_registry.register("refund", RefundTool())
tool_registry.register("create_ticket", TicketTool())


# ---- EXECUTOR ----
executor = Executor(tool_registry=tool_registry)


# ---- ORCHESTRATOR ----
orchestrator = Orchestrator(executor=executor)
