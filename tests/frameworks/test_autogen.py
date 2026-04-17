import pytest
import app.core.container as container

from app.frameworks.autogen.runner import AutoGenAdapter


@pytest.mark.asyncio
async def test_autogen_basic():
    container._orchestrator = None

    adapter = AutoGenAdapter()

    result = await adapter.run("Track ORD1")

    assert result["response"] is not None
    assert "plan" in result
