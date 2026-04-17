from app.frameworks.core.orchestrator_wrapper import OrchestratorWrapper

wrapper = OrchestratorWrapper()


class ToolAgent:
    """
    Only agent allowed to execute.
    """

    async def run(self, query: str):
        return await wrapper.run(query)


class PlannerAgent:
    """
    Simulates planning via conversation.
    """

    def plan(self, query: str):
        # fake "planning"
        return f"Execute: {query}"


class UserAgent:
    """
    Entry point.
    """

    def __init__(self):
        self.planner = PlannerAgent()
        self.tool = ToolAgent()

    async def run(self, query: str):
        plan = self.planner.plan(query)

        # simulate agent communication overhead
        result = await self.tool.run(query)

        return {
            "plan": plan,
            "response": result["response"],
            "trace": result["trace"],
        }
