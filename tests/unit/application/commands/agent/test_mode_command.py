from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.commands.agent.mode_commands import ModeCommand


class _SessionManagerStub:
    def __init__(
        self,
        *,
        mode: str,
        exists: dict[tuple[str, str | None], bool] | None = None,
        recent: dict | None = None,
        sessions: list[dict] | None = None,
        created: str = "new-session",
        memory_manager=None,
    ) -> None:
        self.mode = mode
        self._exists = exists or {}
        self._recent = recent
        self._sessions = sessions or []
        self._created = created
        self.memory_manager = memory_manager

    def get_most_recent_session(self, mode: str | None = None):
        return self._recent

    def session_exists(self, session_id: str, mode: str | None = None) -> bool:
        return self._exists.get((session_id, mode), self._exists.get((session_id, None), False))

    def create_new_session(self):
        return self._created

    def list_sessions(self, mode: str | None = None):
        return self._sessions


class _Ctx:
    def __init__(self) -> None:
        self.current_engine = "agent"
        self.session_id = "basic-current"
        self.console = MagicMock()
        self.project_context = None
        self.metadata_manager = None
        self.deep_checkpointer = None
        self.basic_checkpointer = None
        self.llm_memory = None
        self.memory_sync = "sync"
        self.global_memory = "global"
        self.session_manager = _SessionManagerStub(mode="basic")
        self._configs = {
            "agent": {
                "agent_type": "basic",
                "agent_instance": object(),
                "streaming": True,
            }
        }

    def get_engine_config(self, engine: str):
        return self._configs.setdefault(engine, {})


def test_mode_command_reports_current_mode_when_no_args():
    command = ModeCommand()
    ctx = _Ctx()

    result = asyncio.run(command.execute(ctx, ""))

    assert result.type == "info"
    assert "Current agent mode: basic" in result.message


def test_mode_command_rejects_invalid_target():
    command = ModeCommand()
    ctx = _Ctx()

    result = asyncio.run(command.execute(ctx, "invalid"))

    assert result.type == "error"
    assert "Usage: /mode <basic|deep>" in result.message


def test_mode_command_short_circuits_when_target_equals_current():
    command = ModeCommand()
    ctx = _Ctx()

    result = asyncio.run(command.execute(ctx, "basic"))

    assert result.type == "info"
    assert "already set to basic" in result.message.lower()


def test_mode_command_switches_basic_to_deep_and_initializes_agent(monkeypatch):
    command = ModeCommand()
    ctx = _Ctx()
    deep_manager = _SessionManagerStub(mode="deep", created="deep-created")

    class _Registry:
        @staticmethod
        def list_providers():
            return {"zhipu": {"models": {"glm-4.6": {}, "other": {}}}}

    monkeypatch.setattr("src.core.providers.deepagents_provider_registry", _Registry())
    monkeypatch.setattr(
        "src.components.shared.memory.SessionManager",
        lambda **kwargs: deep_manager,
    )
    monkeypatch.setattr(
        "src.components.shared.memory.DeepAgentCheckpointer",
        lambda **kwargs: "deep-checkpointer",
    )
    monkeypatch.setattr(
        "src.application.services.agent.deep.agent_lifecycle.create_default_deep_agent",
        AsyncMock(return_value=("deep-agent", {"provider": "zhipu", "model": "glm-4.6", "function_type": "research", "tool_count": 5})),
    )

    result = asyncio.run(command.execute(ctx, "deep"))

    config = ctx.get_engine_config("agent")
    assert result.type == "success"
    assert "Switched to deep agent mode. Agent initialized" in result.message
    assert config["agent_type"] == "deep"
    assert config["provider"] == "zhipu"
    assert config["model"] == "glm-4.6"
    assert config["agent_instance"] == "deep-agent"
    assert ctx._basic_session_id == "basic-current"
    assert ctx.session_manager is deep_manager
    assert ctx.session_id == "deep-created"


def test_mode_command_switches_to_deep_even_if_default_init_fails(monkeypatch):
    command = ModeCommand()
    ctx = _Ctx()

    class _Registry:
        @staticmethod
        def list_providers():
            return {"zhipu": {"models": {"glm-4.6": {}}}}

    monkeypatch.setattr("src.core.providers.deepagents_provider_registry", _Registry())
    monkeypatch.setattr(
        "src.components.shared.memory.SessionManager",
        lambda **kwargs: _SessionManagerStub(mode="deep", created="deep-created"),
    )
    monkeypatch.setattr(
        "src.components.shared.memory.DeepAgentCheckpointer",
        lambda **kwargs: "deep-checkpointer",
    )
    monkeypatch.setattr(
        "src.application.services.agent.deep.agent_lifecycle.create_default_deep_agent",
        AsyncMock(side_effect=RuntimeError("init failed")),
    )

    result = asyncio.run(command.execute(ctx, "deep"))

    assert result.type == "success"
    assert "will be initialized on first use" in result.message
    assert ctx.get_engine_config("agent")["agent_type"] == "deep"


def test_mode_command_switches_deep_to_basic_and_restores_basic_session(monkeypatch):
    command = ModeCommand()
    ctx = _Ctx()
    ctx.session_id = "deep-current"
    ctx._basic_session_id = "basic-restore"
    ctx.session_manager = _SessionManagerStub(
        mode="deep",
        exists={("basic-restore", "basic"): True},
    )
    ctx.get_engine_config("agent").update(
        {
            "agent_type": "deep",
            "function_type": "research",
            "middleware": {"m": 1},
            "provider": "zhipu",
            "model": "glm-4.6",
        }
    )

    monkeypatch.setattr(
        "src.components.shared.memory.BasicAgentCheckpointer",
        lambda **kwargs: "basic-checkpointer",
    )
    monkeypatch.setattr(
        "src.components.shared.memory.LLMMemory",
        lambda **kwargs: "llm-memory",
    )
    monkeypatch.setattr(
        "src.application.services.agent.basic.agent_lifecycle.create_default_agent",
        AsyncMock(return_value=("basic-agent", {"provider": "openai", "model": "gpt-4o", "tool_count": 3})),
    )

    result = asyncio.run(command.execute(ctx, "basic"))

    config = ctx.get_engine_config("agent")
    assert result.type == "success"
    assert "Switched to basic agent mode. Agent initialized" in result.message
    assert config["agent_type"] == "basic"
    assert config["agent_instance"] == "basic-agent"
    assert "function_type" not in config
    assert "middleware" not in config
    assert "provider" not in config
    assert "model" not in config
    assert ctx.session_id == "basic-restore"
    assert ctx.session_manager.mode == "basic"
    assert ctx.basic_checkpointer == "basic-checkpointer"
    assert ctx.llm_memory == "llm-memory"


def test_mode_command_switches_to_basic_when_init_fails(monkeypatch):
    command = ModeCommand()
    ctx = _Ctx()
    ctx.get_engine_config("agent")["agent_type"] = "deep"
    ctx.session_manager = _SessionManagerStub(mode="deep", sessions=[], created="basic-created")

    monkeypatch.setattr(
        "src.components.shared.memory.BasicAgentCheckpointer",
        lambda **kwargs: "basic-checkpointer",
    )
    monkeypatch.setattr(
        "src.components.shared.memory.LLMMemory",
        lambda **kwargs: "llm-memory",
    )
    monkeypatch.setattr(
        "src.application.services.agent.basic.agent_lifecycle.create_default_agent",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    result = asyncio.run(command.execute(ctx, "basic"))

    assert result.type == "success"
    assert "will be initialized on first use" in result.message
    assert ctx.get_engine_config("agent")["agent_type"] == "basic"
