import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.services.agent.deep.service import DeepAgentService


class _Ctx:
    def __init__(self) -> None:
        self.session_id = "sess-deep"
        self.console = MagicMock()
        self._configs = {
            "agent": {
                "agent_type": "deep",
                "function_type": "research",
                "streaming": True,
                "agent_instance": None,
                "provider": "zhipu",
                "model": "glm-4.6",
            }
        }

    def get_engine_config(self, engine: str):
        return self._configs.setdefault(engine, {})


def test_initialize_returns_error_when_no_deep_providers():
    ctx = _Ctx()
    service = DeepAgentService()

    with patch(
        "src.application.services.agent.deep.service.deepagents_provider_registry.get_available_providers",
        return_value=[],
    ):
        result = asyncio.run(service.initialize(ctx))

    assert result["type"] == "error"
    assert "No deep agent providers available" in result["message"]


def test_initialize_creates_default_agent_and_updates_config():
    ctx = _Ctx()
    service = DeepAgentService()
    agent = MagicMock()
    info = {
        "provider": "zhipu",
        "model": "glm-4.6",
        "middleware": {"shell": {"enabled": True}},
        "tool_count": 4,
    }

    with patch(
        "src.application.services.agent.deep.service.deepagents_provider_registry.get_available_providers",
        return_value=["zhipu"],
    ), patch(
        "src.application.services.agent.deep.service.create_default_deep_agent",
        new=AsyncMock(return_value=(agent, info)),
    ) as mock_create:
        result = asyncio.run(service.initialize(ctx))

    assert result["type"] == "success"
    assert result["payload"]["mode"]["agent_type"] == "deep"
    assert result["payload"]["agent"] == info
    assert ctx.get_engine_config("agent")["agent_instance"] is agent
    assert ctx.get_engine_config("agent")["provider"] == "zhipu"
    assert ctx.get_engine_config("agent")["model"] == "glm-4.6"
    assert ctx.get_engine_config("agent")["middleware"] == {"shell": {"enabled": True}}
    mock_create.assert_awaited_once_with(ctx, target="deep")


def test_switch_model_requires_provider_when_config_missing():
    ctx = _Ctx()
    ctx.get_engine_config("agent")["provider"] = None
    service = DeepAgentService()

    with patch(
        "src.application.services.agent.deep.service.deepagents_provider_registry.get_available_providers",
        return_value=["zhipu"],
    ):
        result = asyncio.run(service.switch_model(ctx, provider="", model=None))

    assert result["type"] == "error"
    assert "Provider must be specified" in result["message"]


def test_switch_model_rejects_unsupported_provider():
    ctx = _Ctx()
    service = DeepAgentService()

    with patch(
        "src.application.services.agent.deep.service.deepagents_provider_registry.get_available_providers",
        return_value=["zhipu"],
    ):
        result = asyncio.run(service.switch_model(ctx, provider="openai", model="gpt-4o"))

    assert result["type"] == "error"
    assert "Unsupported deep agent provider" in result["message"]


def test_switch_model_success_uses_lifecycle_switch():
    ctx = _Ctx()
    service = DeepAgentService()
    agent = MagicMock()
    info = {"provider": "zhipu", "model": "glm-4.6", "middleware": {}}

    with patch(
        "src.application.services.agent.deep.service.deepagents_provider_registry.get_available_providers",
        return_value=["zhipu"],
    ), patch(
        "src.application.services.agent.deep.service.switch_deep_agent",
        new=AsyncMock(return_value=(agent, info)),
    ) as mock_switch:
        result = asyncio.run(service.switch_model(ctx, provider="zhipu", model="glm-4.6"))

    assert result["type"] == "success"
    assert result["payload"]["agent"] == info
    assert ctx.get_engine_config("agent")["agent_instance"] is agent
    mock_switch.assert_awaited_once_with(
        ctx,
        provider="zhipu",
        model="glm-4.6",
        target="deep",
        function_type="research",
    )


def test_get_info_returns_fallback_when_agent_not_initialized():
    ctx = _Ctx()
    service = DeepAgentService()

    info = service.get_info(ctx)

    assert info["agent"]["status"] == "not_initialized"
    assert info["mode"]["agent_type"] == "deep"


def test_handle_query_delegates_to_conversation_layer():
    ctx = _Ctx()
    service = DeepAgentService()

    with patch(
        "src.application.services.agent.deep.service.handle_deep_agent_query",
        new=AsyncMock(return_value="deep-answer"),
    ) as mock_handle:
        result = asyncio.run(service.handle_query(ctx, "question"))

    assert result == "deep-answer"
    mock_handle.assert_awaited_once_with(ctx, "question")
