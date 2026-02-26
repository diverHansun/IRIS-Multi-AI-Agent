import pytest
from langchain_core.messages import AIMessage

from src.agents.deepagents.managers import DeepAgentManager


class DummyRuntime:
    async def ainvoke(self, inputs):
        return {"messages": [AIMessage(content="ok")]}


@pytest.mark.asyncio
async def test_create_deep_agent_builds_runtime(monkeypatch):
    manager = DeepAgentManager()

    monkeypatch.setattr(
        "src.components.deepagents.runtime.create_deep_agent_runtime",
        lambda **kwargs: DummyRuntime(),
    )

    agent = await manager.create_deep_agent(
        provider="ANTHROPIC",
        model="claude-4.5-sonnet",
        function_type="coding",
    )

    assert agent.function_type == "coding"
    result = await agent.ainvoke("test query")
    assert result["success"] is True
    assert "ok" in result["output"]


@pytest.mark.asyncio
async def test_create_deep_agent_uses_default_model(monkeypatch):
    manager = DeepAgentManager()

    monkeypatch.setattr(
        "src.components.deepagents.runtime.create_deep_agent_runtime",
        lambda **kwargs: DummyRuntime(),
    )

    agent = await manager.create_deep_agent(
        provider="ZHIPU",
        model=None,
        function_type="research",
    )

    info = agent.get_info()
    assert info["provider"] == "ZHIPU"
    assert info["model"] == "glm-4.6"
    assert info["model_identifier"] == "openai:glm-4.6"
