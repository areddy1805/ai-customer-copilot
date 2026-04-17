from app.frameworks.autogen.agents import UserAgent


class AutoGenAdapter:
    """
    Simulated multi-agent system.
    """

    def __init__(self):
        self.agent = UserAgent()

    async def run(self, query: str):
        return await self.agent.run(query)
