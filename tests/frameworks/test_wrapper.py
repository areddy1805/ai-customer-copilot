import pytest

from app.frameworks.core.orchestrator_wrapper import OrchestratorWrapper
import app.core.container as container


@pytest.mark.asyncio
async def test_wrapper_basic():
    # reset singleton
    container._orchestrator = None

    wrapper = OrchestratorWrapper()

    result = await wrapper.run("Track ORD1")

    assert "response" in result
    assert "trace" in result
    assert result["query"] == "Track ORD1"
