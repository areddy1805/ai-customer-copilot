import asyncio
from langchain.tools import tool

from app.frameworks.core.orchestrator_wrapper import OrchestratorWrapper

wrapper = OrchestratorWrapper()


@tool
def orchestrator_tool(query: str) -> str:
    """
    Execute user query via deterministic orchestrator system.

    This tool routes all requests to the internal execution engine
    which handles planning, tool execution, RAG, and response generation.
    """

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    result = loop.run_until_complete(wrapper.run(query))

    loop.close()

    return result["response"]
