import asyncio
from app.orchestrator.executor import ToolResult


class RAGTool:
    def __init__(self, rag_service):
        self.rag = rag_service

    def generate(self, inputs: dict):
        query = inputs.get("query")

        if not query:
            return ToolResult(success=False, error="Missing query")

        try:
            # SAFE EXECUTION INSIDE SYNC CONTEXT
            loop = asyncio.get_event_loop()
            if loop.is_running():
                result = asyncio.run_coroutine_threadsafe(
                    self.rag.generate(query), loop
                ).result()
            else:
                result = asyncio.run(self.rag.generate(query))

            return ToolResult(success=True, data={"response": result})

        except Exception as e:
            return ToolResult(success=False, error=str(e))
