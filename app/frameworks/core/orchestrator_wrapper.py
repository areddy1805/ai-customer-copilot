from typing import Any, Dict

from app.core.container import get_orchestrator
from app.core.config import settings


class OrchestratorWrapper:
    def __init__(self):
        self.orchestrator = get_orchestrator()

    async def run(self, query: str, session_id: str = "framework") -> Dict[str, Any]:
        state = await self.orchestrator.run(user_query=query, session_id=session_id)

        return {
            "query": query,
            "response": state.final_response,
            "trace": state.trace,
            "meta": {"provider": settings.LLM_PROVIDER, "mode": "framework_adapter"},
        }
