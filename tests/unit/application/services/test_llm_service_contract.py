import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.services.llm.service import LLMService


class _Ctx:
    def __init__(self) -> None:
        self.session_id = "sess-llm"
        self.console = MagicMock()
        self._configs = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4o",
                "streaming": True,
                "llm_instance": None,
            }
        }

    def get_engine_config(self, engine: str):
        return self._configs.setdefault(engine, {})


def test_initialize_success_sets_instance_and_returns_payload():
    ctx = _Ctx()
    service = LLMService()
    llm = MagicMock()
    llm.model = "gpt-4.1"

    with patch(
        "src.application.services.llm.service.create_llm",
        new=AsyncMock(return_value=llm),
    ) as mock_create, patch(
        "src.application.services.llm.service.get_llm_info",
        return_value={
            "provider": "openai",
            "model": "gpt-4.1",
            "model_name": "GPT-4.1",
            "description": "desc",
        },
    ), patch(
        "src.application.services.llm.service.register_llm"
    ) as mock_register:
        result = asyncio.run(service.initialize(ctx))

    assert result["type"] == "success"
    assert result["payload"]["mode"]["mode"] == "llm"
    assert result["payload"]["agent"]["model"] == "gpt-4.1"
    assert ctx.get_engine_config("llm")["llm_instance"] is llm
    assert ctx.get_engine_config("llm")["model"] == "gpt-4.1"
    mock_create.assert_awaited_once_with("openai", "gpt-4o", mode="llm")
    mock_register.assert_called_once_with("openai", llm)


def test_initialize_returns_error_when_create_llm_fails():
    ctx = _Ctx()
    service = LLMService()

    with patch(
        "src.application.services.llm.service.create_llm",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = asyncio.run(service.initialize(ctx))

    assert result["type"] == "error"
    assert "Failed to initialize LLM engine" in result["message"]


def test_handle_query_delegates_to_conversation_handler():
    ctx = _Ctx()
    llm = MagicMock()
    ctx.get_engine_config("llm")["llm_instance"] = llm
    service = LLMService()

    with patch(
        "src.application.services.llm.service.handle_llm_query",
        new=AsyncMock(return_value="answer"),
    ) as mock_handle:
        result = asyncio.run(service.handle_query(ctx, "hello"))

    assert result == "answer"
    mock_handle.assert_awaited_once_with(
        ctx,
        llm,
        "openai",
        "hello",
        streaming=True,
    )


def test_switch_model_success_recreates_llm_and_returns_success():
    ctx = _Ctx()
    old_instance = object()
    ctx.get_engine_config("llm")["llm_instance"] = old_instance
    service = LLMService()
    new_llm = MagicMock()
    new_llm.model = "gpt-4.1"

    with patch(
        "src.application.services.llm.service.create_llm",
        new=AsyncMock(return_value=new_llm),
    ), patch(
        "src.application.services.llm.service.get_llm_info",
        return_value={"provider": "openai", "model": "gpt-4.1", "model_name": "GPT-4.1"},
    ), patch(
        "src.application.services.llm.service.register_llm"
    ):
        result = asyncio.run(service.switch_model(ctx, "openai", "gpt-4.1"))

    assert result["type"] == "success"
    assert "Switched to openai / gpt-4.1" in result["message"]
    assert ctx.get_engine_config("llm")["llm_instance"] is new_llm
    assert ctx.get_engine_config("llm")["provider"] == "openai"
    assert ctx.get_engine_config("llm")["model"] == "gpt-4.1"


def test_switch_model_returns_error_when_creation_fails():
    ctx = _Ctx()
    service = LLMService()

    with patch(
        "src.application.services.llm.service.create_llm",
        new=AsyncMock(side_effect=RuntimeError("invalid model")),
    ):
        result = asyncio.run(service.switch_model(ctx, "openai", "broken"))

    assert result["type"] == "error"
    assert "Failed to switch LLM" in result["message"]
