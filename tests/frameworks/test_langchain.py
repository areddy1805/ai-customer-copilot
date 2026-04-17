import app.core.container as container
from app.frameworks.langchain.agent import LangChainAdapter


def test_langchain_basic():
    container._orchestrator = None

    agent = LangChainAdapter()

    response = agent.run("Track ORD1")

    assert response is not None
    assert isinstance(response, str)
