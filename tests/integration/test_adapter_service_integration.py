import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.engine_adapters.agent_adapter import AgentAdapter
from src.application.engine_adapters.dify_adapter import DifyAdapter
from src.application.engine_adapters.llm_adapter import LLMAdapter


class _Ctx:
    def __init__(self, *, agent_type: str = "basic", has_agent_instance: bool = False, has_llm: bool = False) -> None:
        self.current_engine = "agent"
        self.session_id = "session-adapter"
        self.console = MagicMock()
        self._configs = {
            "llm": {"llm_instance": object() if has_llm else None},
            "agent": {
                "agent_type": agent_type,
                "agent_instance": object() if has_agent_instance else None,
            },
            "dify": {},
        }

    def get_engine_config(self, engine: str):
        return self._configs.setdefault(engine, {})


@pytest.mark.asyncio
async def test_llm_adapter_initializes_before_handle_when_missing_instance():
    ctx = _Ctx(has_llm=False)
    adapter = LLMAdapter()

    with patch(
        "src.application.engine_adapters.llm_adapter.LLMService.initialize",
        new=AsyncMock(return_value={"type": "success"}),
    ) as mock_init, patch(
        "src.application.engine_adapters.llm_adapter.LLMService.handle_query",
        new=AsyncMock(return_value="llm-answer"),
    ) as mock_handle:
        result = await adapter.handle_query(ctx, "hello")

    assert result == "llm-answer"
    mock_init.assert_awaited_once_with(ctx)
    mock_handle.assert_awaited_once_with(ctx, "hello")


@pytest.mark.asyncio
async def test_llm_adapter_skips_initialize_when_instance_exists():
    ctx = _Ctx(has_llm=True)
    adapter = LLMAdapter()

    with patch(
        "src.application.engine_adapters.llm_adapter.LLMService.initialize",
        new=AsyncMock(),
    ) as mock_init, patch(
        "src.application.engine_adapters.llm_adapter.LLMService.handle_query",
        new=AsyncMock(return_value="ok"),
    ) as mock_handle:
        result = await adapter.handle_query(ctx, "q")

    assert result == "ok"
    mock_init.assert_not_awaited()
    mock_handle.assert_awaited_once_with(ctx, "q")


@pytest.mark.asyncio
async def test_agent_adapter_routes_to_deep_service_and_initializes():
    ctx = _Ctx(agent_type="deep", has_agent_instance=False)
    adapter = AgentAdapter()

    with patch(
        "src.application.engine_adapters.agent_adapter.DeepAgentService.initialize",
        new=AsyncMock(return_value={"type": "success"}),
    ) as mock_init, patch(
        "src.application.engine_adapters.agent_adapter.DeepAgentService.handle_query",
        new=AsyncMock(return_value="deep-answer"),
    ) as mock_handle:
        result = await adapter.handle_query(ctx, "research")

    assert result == "deep-answer"
    mock_init.assert_awaited_once_with(ctx)
    mock_handle.assert_awaited_once_with(ctx, "research")


@pytest.mark.asyncio
async def test_agent_adapter_routes_to_basic_service():
    ctx = _Ctx(agent_type="basic", has_agent_instance=True)
    adapter = AgentAdapter()

    with patch(
        "src.application.engine_adapters.agent_adapter.BasicAgentService.initialize",
        new=AsyncMock(),
    ) as mock_init, patch(
        "src.application.engine_adapters.agent_adapter.BasicAgentService.handle_query",
        new=AsyncMock(return_value="basic-answer"),
    ) as mock_handle:
        result = await adapter.handle_query(ctx, "task")

    assert result == "basic-answer"
    mock_init.assert_not_awaited()
    mock_handle.assert_awaited_once_with(ctx, "task")


@pytest.mark.asyncio
async def test_dify_adapter_forwards_to_dify_service():
    ctx = _Ctx()
    adapter = DifyAdapter()

    with patch(
        "src.application.engine_adapters.dify_adapter.DifyService.handle_query",
        new=AsyncMock(return_value=""),
    ) as mock_handle:
        result = await adapter.handle_query(ctx, "question")

    assert result == ""
    mock_handle.assert_awaited_once_with(ctx, "question")
