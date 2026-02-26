import pytest
from types import SimpleNamespace

from src.application.services.agent.deep.streaming import conversation as conv


class DummyConsole:
    def __init__(self):
        self.messages = []

    def print(self, message, *args, **kwargs):
        self.messages.append(str(message))


class DummyRuntime:
    def __init__(self):
        self.aupdate_calls = []

    async def astream(self, *args, **kwargs):
        raise KeyboardInterrupt()
        yield  # pragma: no cover - generator requirement

    async def aupdate_state(self, config, values):
        self.aupdate_calls.append((config, values))


class DummySessionContext:
    def __init__(self, session_id: str):
        self.session_id = session_id

    def build_runtime_config(self, config):
        return config


class DummyAgent:
    def __init__(self):
        self.runtime = DummyRuntime()
        self.metadata = {}
        self.memory_sync = None
        self.runtime_checkpointer = None

    def create_runtime_config(self, session_id):
        return {"thread_id": "thread-1"}

    def create_session_context(self, session_id):
        return DummySessionContext(session_id)

    def create_runtime_input(self, query):
        return {"input": query}

    def prepare_stream_result(self, query, session_id, final_state, tool_stats):
        return {"success": True, "output": ""}

    def update_session_checkpoint(self, session_ctx):
        # No-op for testing
        return None


class DummyEventHandler:
    def __init__(self, console, **kwargs):
        self.console = console
        self.last_agent_state = {}
        self.tool_stats = {"tool_calls": 0, "tool_names": []}

    def handle_event(self, event):
        class Result:
            def __init__(self):
                self.interrupts = None
                self.final_state = None

        return Result()

    def render_summary(self):
        return None


@pytest.mark.asyncio
async def test_handle_deep_agent_query_handles_keyboard_interrupt(monkeypatch):
    """DeepAgent should persist and notify runtime on interrupt without crashing."""
    persisted = {}

    async def fake_persist(ctx, session_ctx, runtime_checkpointer, runtime_config, agent_memory_sync, reason="normal"):
        persisted["reason"] = reason
        persisted["session_id"] = session_ctx.session_id
        persisted["runtime_config"] = runtime_config
        return True

    monkeypatch.setattr(conv, "_persist_conversation_state", fake_persist)
    monkeypatch.setattr(conv, "DeepAgentEventHandler", DummyEventHandler)
    monkeypatch.setattr(conv, "_ensure_hitl_manager", lambda ctx, hitl_config: SimpleNamespace())
    monkeypatch.setattr(conv, "FileOpTracker", lambda *args, **kwargs: SimpleNamespace())

    agent = DummyAgent()
    config = {"agent_instance": agent, "agent_type": "deep", "provider": "unit-test"}
    console = DummyConsole()
    ctx = SimpleNamespace(console=console, session_id="s-test", memory_sync=None, hitl_manager=None)
    ctx.get_engine_config = lambda engine="agent": config

    result = await conv.handle_deep_agent_query(ctx, "hello")

    assert result == ""
    assert persisted["reason"] == "user_interrupt"
    assert agent.runtime.aupdate_calls
    message = agent.runtime.aupdate_calls[0][1]["messages"][0].content
    assert "Ctrl+C" in message
    assert any("Interrupted" in msg or "Execution interrupted" in msg for msg in console.messages)
