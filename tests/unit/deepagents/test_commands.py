import pytest

from src.application.commands.agent.deep.use_commands import UseCommand


class DummyCtx:
    current_engine = "agent"

    def __init__(self, agent_config):
        self._agent_config = agent_config

    def get_engine_config(self, key):
        assert key == "agent"
        return self._agent_config


class DummyAgent:
    def __init__(self):
        self.info = {"provider": "ANTHROPIC", "model": "claude-4.5-sonnet", "middleware": {}}

    def get_info(self):
        return self.info


@pytest.mark.asyncio
async def test_use_command_lists_available_functions(monkeypatch):
    command = UseCommand()
    monkeypatch.setattr(
        "src.application.commands.agent.deep.use_commands.deep_agent_manager.get_available_functions",
        lambda: {
            "research": {"description": "Research orchestrator"},
            "coding": {"description": "Coding assistant"},
        },
    )

    result = await command.execute(DummyCtx({"agent_type": "deep"}), "")

    assert result.type == "info"
    assert "research" in result.message
    assert "coding" in result.message


@pytest.mark.asyncio
async def test_use_command_sets_function_in_basic_mode(monkeypatch):
    command = UseCommand()
    agent_config = {
        "agent_type": "basic",
        "function_type": "research",
        "agent_instance": None,
    }

    monkeypatch.setattr(
        "src.application.commands.agent.deep.use_commands.deep_agent_manager.get_available_functions",
        lambda: {"coding": {"description": "Coding assistant"}},
    )
    monkeypatch.setattr(
        "src.application.commands.agent.deep.use_commands.switch_deep_agent",
        lambda *args, **kwargs: pytest.fail("switch_deep_agent should not be called in basic mode"),
    )

    result = await command.execute(DummyCtx(agent_config), "coding")

    assert result.type == "success"
    assert agent_config["function_type"] == "coding"
    assert agent_config["agent_instance"] is None
    assert "Switch to deep mode" in result.message or "Deep agent function set to coding" in result.message


@pytest.mark.asyncio
async def test_use_command_switches_in_deep_mode(monkeypatch):
    command = UseCommand()
    agent_config = {
        "agent_type": "deep",
        "function_type": "research",
        "provider": "ANTHROPIC",
        "model": "claude-4.5-sonnet",
        "agent_instance": None,
    }

    monkeypatch.setattr(
        "src.application.commands.agent.deep.use_commands.deep_agent_manager.get_available_functions",
        lambda: {"analysis": {"description": "Analysis specialist"}},
    )

    async def fake_switch(ctx, provider, model, target, function_type):
        assert target == "deep"
        assert function_type == "analysis"
        return DummyAgent(), {"provider": provider, "model": model, "middleware": {}, "function_type": function_type}

    monkeypatch.setattr(
        "src.application.commands.agent.deep.use_commands.switch_deep_agent",
        fake_switch,
    )

    result = await command.execute(DummyCtx(agent_config), "analysis")

    assert result.type == "success"
    assert agent_config["function_type"] == "analysis"
    assert isinstance(agent_config["agent_instance"], DummyAgent)
