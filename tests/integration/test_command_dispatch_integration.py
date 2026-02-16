import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.commands import dispatch


class _Ctx:
    def __init__(self, *, engine: str, agent_type: str = "basic") -> None:
        self.current_engine = engine
        self.session_id = "session-dispatch"
        self.console = MagicMock()
        self.engine_configs = {
            "llm": {"provider": "openai", "model": "gpt-4o"},
            "agent": {"agent_type": agent_type},
            "agentflow": {},
            "dify": {},
        }

    def get_engine_config(self, engine: str):
        return self.engine_configs.setdefault(engine, {})


@pytest.mark.asyncio
async def test_dispatch_model_routes_to_llm_command_in_llm_engine():
    ctx = _Ctx(engine="llm")

    with patch(
        "src.application.commands.llm.model_commands.LLMService.switch_model",
        new=AsyncMock(return_value={"type": "success", "message": "ok", "payload": {"k": "v"}}),
    ) as mock_switch:
        result = await dispatch("model", ctx, "openai gpt-4o")

    assert result.type == "success"
    assert result.message == "ok"
    assert result.payload == {"k": "v"}
    mock_switch.assert_awaited_once_with(ctx, "openai", "gpt-4o")


@pytest.mark.asyncio
async def test_dispatch_model_routes_to_deep_agent_command_in_agent_deep_mode():
    ctx = _Ctx(engine="agent", agent_type="deep")

    with patch(
        "src.application.commands.agent.model_commands.DeepAgentService.switch_model",
        new=AsyncMock(return_value={"type": "success", "message": "deep-ok", "payload": {}}),
    ) as mock_switch:
        result = await dispatch("model", ctx, "zhipu glm-4.6")

    assert result.type == "success"
    assert result.message == "deep-ok"
    mock_switch.assert_awaited_once_with(ctx, "zhipu", "glm-4.6")


@pytest.mark.asyncio
async def test_dispatch_model_routes_to_basic_agent_command_in_agent_basic_mode():
    ctx = _Ctx(engine="agent", agent_type="basic")

    with patch(
        "src.application.commands.agent.model_commands.BasicAgentService.switch_model",
        new=AsyncMock(return_value={"type": "success", "message": "basic-ok", "payload": {}}),
    ) as mock_switch:
        result = await dispatch("model", ctx, "openai gpt-4o")

    assert result.type == "success"
    assert result.message == "basic-ok"
    mock_switch.assert_awaited_once_with(ctx, "openai", "gpt-4o")


@pytest.mark.asyncio
async def test_dispatch_model_rejected_in_dify_engine():
    ctx = _Ctx(engine="dify")

    result = await dispatch("model", ctx, "openai gpt-4o")

    assert result.type == "error"
    assert "not available" in result.message


@pytest.mark.asyncio
async def test_dispatch_unknown_command_returns_error():
    ctx = _Ctx(engine="llm")

    result = await dispatch("unknown-command", ctx, "")

    assert result.type == "error"
    assert "Unknown command" in result.message
