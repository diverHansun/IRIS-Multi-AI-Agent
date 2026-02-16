import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.services.agent.basic.service import BasicAgentService


class _Ctx:
    def __init__(self) -> None:
        self.session_id = "sess-basic"
        self.console = MagicMock()
        self._configs = {
            "agent": {
                "agent_type": "basic",
                "streaming": True,
                "agent_instance": None,
            }
        }

    def get_engine_config(self, engine: str):
        return self._configs.setdefault(engine, {})


def test_initialize_returns_error_when_no_providers():
    ctx = _Ctx()
    service = BasicAgentService()

    with patch(
        "src.application.services.agent.basic.service.agent_manager.get_available_agents",
        return_value=[],
    ):
        result = asyncio.run(service.initialize(ctx))

    assert result["type"] == "error"
    assert "No agent providers available" in result["message"]


def test_initialize_creates_default_agent_when_missing():
    ctx = _Ctx()
    service = BasicAgentService()
    agent = MagicMock()
    info = {"provider": "zhipu", "model": "glm-4.6", "tool_count": 3}

    with patch(
        "src.application.services.agent.basic.service.agent_manager.get_available_agents",
        return_value=[{"provider": "zhipu"}],
    ), patch(
        "src.application.services.agent.basic.service.create_default_agent",
        new=AsyncMock(return_value=(agent, info)),
    ) as mock_create:
        result = asyncio.run(service.initialize(ctx))

    assert result["type"] == "success"
    assert result["payload"]["agent"] == info
    assert result["payload"]["mode"]["agent_type"] == "basic"
    assert ctx.get_engine_config("agent")["agent_instance"] is agent
    mock_create.assert_awaited_once_with(ctx, target="basic")


def test_initialize_reuses_existing_agent_and_registers_llm():
    ctx = _Ctx()
    agent = MagicMock()
    agent.get_info.return_value = {"provider": "openai", "model": "gpt-4o"}
    agent.get_llm.return_value = "llm-instance"
    ctx.get_engine_config("agent")["agent_instance"] = agent
    service = BasicAgentService()

    with patch(
        "src.application.services.agent.basic.service.agent_manager.get_available_agents",
        return_value=[{"provider": "openai"}],
    ), patch(
        "src.application.services.agent.basic.service.register_llm"
    ) as mock_register:
        result = asyncio.run(service.initialize(ctx))

    assert result["type"] == "success"
    assert result["payload"]["agent"]["provider"] == "openai"
    mock_register.assert_called_once_with("openai", "llm-instance")


def test_switch_model_rejects_unsupported_provider():
    ctx = _Ctx()
    service = BasicAgentService()

    with patch(
        "src.application.services.agent.basic.service.agent_manager.get_available_agents",
        return_value=[{"provider": "zhipu"}],
    ):
        result = asyncio.run(service.switch_model(ctx, "openai", "gpt-4o"))

    assert result["type"] == "error"
    assert "Unsupported agent provider" in result["message"]


def test_switch_model_success_updates_instance():
    ctx = _Ctx()
    service = BasicAgentService()
    new_agent = MagicMock()
    info = {"provider": "zhipu", "model": "glm-4.6"}

    with patch(
        "src.application.services.agent.basic.service.agent_manager.get_available_agents",
        return_value=[{"provider": "zhipu"}],
    ), patch(
        "src.application.services.agent.basic.service.switch_agent",
        new=AsyncMock(return_value=(new_agent, info)),
    ) as mock_switch:
        result = asyncio.run(service.switch_model(ctx, "zhipu", "glm-4.6"))

    assert result["type"] == "success"
    assert result["payload"]["agent"] == info
    assert ctx.get_engine_config("agent")["agent_instance"] is new_agent
    mock_switch.assert_awaited_once_with(
        ctx,
        provider="zhipu",
        model="glm-4.6",
        target="basic",
    )


def test_get_info_returns_mode_and_agent_info():
    ctx = _Ctx()
    service = BasicAgentService()
    agent = MagicMock()
    agent.get_info.return_value = {"provider": "zhipu", "model": "glm-4.6"}
    ctx.get_engine_config("agent")["agent_instance"] = agent

    info = service.get_info(ctx)

    assert info["agent"]["provider"] == "zhipu"
    assert info["mode"]["mode"] == "agent"
    assert info["mode"]["agent_type"] == "basic"
