import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.application.services.dify.service import DifyService


class _Ctx:
    def __init__(self) -> None:
        self.session_id = "sess-dify"
        self.console = MagicMock()
        self._configs = {"dify": {}}

    def get_engine_config(self, engine: str):
        return self._configs.setdefault(engine, {})


class _RuntimeStub:
    def __init__(
        self,
        *,
        init_result=None,
        query_result=None,
        initialized: bool = False,
    ) -> None:
        self.initialized = initialized
        self.conversation_id = "conv-1"
        self.uploaded_files = ["f1", "f2"]
        self._init_result = init_result or {"type": "success", "message": "ready"}
        self._query_result = query_result or {"type": "success", "message": ""}
        self.last_query = None
        self.last_user = None

    async def initialize(self):
        if self._init_result.get("type") != "error":
            self.initialized = True
        return self._init_result

    async def handle_query(self, query: str, user_id: str):
        self.last_query = query
        self.last_user = user_id
        return self._query_result


def test_initialize_success_wraps_runtime_payload():
    ctx = _Ctx()
    service = DifyService()
    runtime = _RuntimeStub()

    with patch.object(service, "_get_runtime", return_value=runtime):
        result = asyncio.run(service.initialize(ctx))

    assert result["type"] == "success"
    assert result["payload"]["agent"]["provider"] == "dify"
    assert result["payload"]["agent"]["model"] == "cloud"
    assert result["payload"]["agent"]["conversation_id"] == "conv-1"
    assert result["payload"]["mode"]["mode"] == "cloud"


def test_initialize_returns_runtime_error_directly():
    ctx = _Ctx()
    service = DifyService()
    runtime = _RuntimeStub(init_result={"type": "error", "message": "bad config"})

    with patch.object(service, "_get_runtime", return_value=runtime):
        result = asyncio.run(service.initialize(ctx))

    assert result["type"] == "error"
    assert result["message"] == "bad config"


def test_handle_query_initializes_runtime_on_demand():
    ctx = _Ctx()
    service = DifyService()
    runtime = _RuntimeStub(initialized=False)

    with patch.object(service, "_get_runtime", return_value=runtime):
        result = asyncio.run(service.handle_query(ctx, "hello"))

    assert result == ""
    assert runtime.last_query == "hello"
    assert runtime.last_user == "sess-dify"


def test_handle_query_prints_error_when_runtime_query_fails():
    ctx = _Ctx()
    service = DifyService()
    runtime = _RuntimeStub(
        initialized=True,
        query_result={"type": "error", "message": "query failed"},
    )

    with patch.object(service, "_get_runtime", return_value=runtime):
        result = asyncio.run(service.handle_query(ctx, "hello"))

    assert result == ""
    assert ctx.console.print.called
    assert "query failed" in str(ctx.console.print.call_args)


def test_switch_model_returns_unsupported_error():
    ctx = _Ctx()
    service = DifyService()

    result = asyncio.run(service.switch_model(ctx, "openai", "gpt-4o"))

    assert result["type"] == "error"
    assert "cannot switch providers" in result["message"].lower()


def test_get_info_reflects_runtime_state():
    ctx = _Ctx()
    service = DifyService()
    runtime = _RuntimeStub(initialized=True)

    with patch.object(service, "_get_runtime", return_value=runtime):
        info = service.get_info(ctx)

    assert info["agent"]["provider"] == "dify"
    assert info["agent"]["model"] == "cloud"
    assert info["agent"]["conversation_id"] == "conv-1"
    assert info["agent"]["files_count"] == 2
    assert info["mode"]["mode"] == "cloud"
