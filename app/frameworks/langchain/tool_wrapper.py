from langchain.tools import tool

from app.frameworks.core.orchestrator_wrapper import OrchestratorWrapper

wrapper = OrchestratorWrapper()


@tool
async def orchestrator_tool(query: str) -> str:
    """
    Execute user query via deterministic orchestrator system.
    """

    result = await wrapper.run(query)

    return result["response"]
