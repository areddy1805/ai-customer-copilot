import pytest
import app.core.container as container

from app.frameworks.langgraph.graph import get_langgraph_app


@pytest.mark.asyncio
async def test_langgraph_basic():
    container._orchestrator = None

    app = get_langgraph_app()

    result = await app.ainvoke({"query": "Track ORD1"})

    assert "response" in result
    assert result["response"] is not None
