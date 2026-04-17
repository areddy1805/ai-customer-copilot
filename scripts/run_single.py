import asyncio
import sys
import json

# --------------------------
# FORCE LOGS → STDERR
# --------------------------
print = lambda *args, **kwargs: __builtins__.print(*args, file=sys.stderr, **kwargs)

from app.frameworks.core.orchestrator_wrapper import OrchestratorWrapper
from app.frameworks.langchain.agent import LangChainAdapter
from app.frameworks.langgraph.graph import get_langgraph_app
from app.frameworks.autogen.runner import AutoGenAdapter


mode = sys.argv[1]
query = sys.argv[2]


async def main():
    if mode == "core":
        wrapper = OrchestratorWrapper()
        result = await wrapper.run(query)
        sys.stdout.write(json.dumps({"response": result["response"]}) + "\n")

    elif mode == "langchain":
        agent = LangChainAdapter()
        res = await agent.run(query)
        sys.stdout.write(json.dumps({"response": res}) + "\n")

    elif mode == "langgraph":
        app = get_langgraph_app()
        result = await app.ainvoke({"query": query})
        sys.stdout.write(json.dumps({"response": result["response"]}) + "\n")

    elif mode == "autogen":
        agent = AutoGenAdapter()
        result = await agent.run(query)
        sys.stdout.write(json.dumps({"response": result["response"]}) + "\n")

    sys.stdout.flush()


asyncio.run(main())
