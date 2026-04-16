_orchestrator = None


def get_orchestrator():
    global _orchestrator

    if _orchestrator is None:
        print("INITIALIZING ORCHESTRATOR (LAZY)")

        from app.orchestrator.orchestrator import Orchestrator
        from app.llm.service import LLMService
        from app.rag.service import RAGService

        from app.tools.order_tool import OrderTool
        from app.tools.refund_tool import RefundTool
        from app.tools.ticket_tool import TicketTool

        llm = LLMService()
        rag = RAGService(llm)

        tools = {
            "order": OrderTool(),
            "refund": RefundTool(),
            "ticket": TicketTool(),
            "rag": rag,
        }

        _orchestrator = Orchestrator(
            tools=tools,
            llm=llm,
            rag=rag,
        )

    return _orchestrator
