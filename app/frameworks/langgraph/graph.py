from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.frameworks.core.orchestrator_wrapper import OrchestratorWrapper


class GraphState(TypedDict):
    query: str
    response: str


wrapper = OrchestratorWrapper()


async def orchestrator_node(state: GraphState):
    result = await wrapper.run(state["query"])

    return {
        "query": state["query"],
        "response": result["response"],
    }


def get_langgraph_app():
    graph = StateGraph(GraphState)

    graph.add_node("orchestrator", orchestrator_node)

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", END)

    return graph.compile()
