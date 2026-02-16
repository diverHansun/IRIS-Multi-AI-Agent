import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.commands.engine_commands import SwitchEngineCommand


class _SessionManagerStub:
    def __init__(self) -> None:
        self.mode = "llm"
        self.memory_manager = None
        self._counter = 0

    def session_exists(self, session_id: str, mode: str):
        return False

    def get_most_recent_session(self, mode: str):
        return None

    def create_new_session(self):
        self._counter += 1
        return f"sess-{self._counter}"

    def list_sessions(self, mode: str):
        return []


class _Ctx:
    def __init__(self, *, current_engine: str = "llm") -> None:
        self.current_engine = current_engine
        self.session_id = None
        self.console = MagicMock()
        self.engine_configs = {
            "llm": {"provider": "openai", "model": "gpt-4o"},
            "agent": {"agent_type": "basic"},
            "agentflow": {},
            "dify": {},
        }
        self.session_manager = _SessionManagerStub()
        self.llm_memory = object()
        self.basic_checkpointer = None
        self.deep_checkpointer = None
        self.memory_sync = None
        self.global_memory = None
        self.project_context = None
        self.metadata_manager = None

    def get_engine_config(self, engine: str):
        return self.engine_configs.setdefault(engine, {})


@pytest.mark.asyncio
async def test_switch_engine_rejects_unknown_engine():
    ctx = _Ctx(current_engine="llm")
    command = SwitchEngineCommand()

    result = await command.execute(ctx, "unknown")

    assert result.type == "error"
    assert "Unknown engine" in result.message


@pytest.mark.asyncio
async def test_switch_engine_returns_info_when_target_is_current():
    ctx = _Ctx(current_engine="llm")
    command = SwitchEngineCommand()

    result = await command.execute(ctx, "llm")

    assert result.type == "info"
    assert "Already using engine 'llm'" in result.message


@pytest.mark.asyncio
async def test_switch_llm_to_dify_calls_target_service_initialize():
    ctx = _Ctx(current_engine="llm")
    command = SwitchEngineCommand()
    fake_service = MagicMock()
    fake_service.initialize = AsyncMock(
        return_value={"type": "success", "message": "dify ready", "payload": {"mode": {"mode": "cloud"}}}
    )

    with patch(
        "src.application.commands.engine_commands.get_current_service",
        return_value=fake_service,
    ):
        result = await command.execute(ctx, "dify")

    assert ctx.current_engine == "dify"
    assert result.type == "success"
    assert result.message == "dify ready"
    assert result.payload == {"mode": {"mode": "cloud"}}
    fake_service.initialize.assert_awaited_once_with(ctx)


@pytest.mark.asyncio
async def test_switch_from_dify_to_llm_triggers_dify_cleanup_then_initialize():
    ctx = _Ctx(current_engine="dify")
    command = SwitchEngineCommand()
    fake_service = MagicMock()
    fake_service.initialize = AsyncMock(
        return_value={"type": "success", "message": "llm ready", "payload": {"mode": {"mode": "llm"}}}
    )

    with patch(
        "src.application.services.dify.DifyService.cleanup",
        new=AsyncMock(),
    ) as mock_cleanup, patch(
        "src.application.commands.engine_commands.get_current_service",
        return_value=fake_service,
    ):
        result = await command.execute(ctx, "llm")

    assert ctx.current_engine == "llm"
    assert result.type == "success"
    assert result.message == "llm ready"
    mock_cleanup.assert_awaited()
    fake_service.initialize.assert_awaited_once_with(ctx)
