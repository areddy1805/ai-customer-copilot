from app.frameworks.langchain.tool_wrapper import orchestrator_tool


class LangChainAdapter:
    """
    LangChain without agent loop.

    Direct tool invocation.
    No LLM control.
    """

    def __init__(self):
        self.tool = orchestrator_tool

    def run(self, query: str) -> str:
        return self.tool.invoke({"query": query})
