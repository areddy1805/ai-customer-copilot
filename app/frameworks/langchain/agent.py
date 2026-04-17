from app.frameworks.langchain.tool_wrapper import orchestrator_tool


class LangChainAdapter:
    def __init__(self):
        self.tool = orchestrator_tool

    async def run(self, query: str) -> str:
        return await self.tool.ainvoke({"query": query})
