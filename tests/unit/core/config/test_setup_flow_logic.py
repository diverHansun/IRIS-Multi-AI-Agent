from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from src.application.commands.shared.setup_commands import SetupCommand
from src.core.config.setup.steps.agent import AgentSetupStep
from src.core.config.setup.steps.base import SetupContext
from src.core.config.setup.steps.llm import LLMSetupStep, Option


class _EnvWriterStub:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def write_key(self, key: str, value: str) -> None:
        self.data[key] = value


def _build_context() -> SetupContext:
    return SetupContext(
        share_dir=Path("."),
        env_writer=_EnvWriterStub(),
        configured_providers=set(),
        console=MagicMock(),
        version="0.0.0",
    )


def test_llm_step_fails_when_default_provider_key_is_empty(monkeypatch):
    step = LLMSetupStep()
    context = _build_context()

    class _Selector:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            return Option(
                key="openai",
                label="openai",
                description="OpenAI GPT",
            )

    answers = iter([
        "",   # OPENAI_API_KEY (empty -> should not count as configured)
        "N",  # Configure another provider?
    ])

    monkeypatch.setattr("src.core.config.setup.steps.llm.SelectOne", _Selector)
    monkeypatch.setattr(
        "src.core.config.setup.steps.llm.Prompt.ask",
        lambda *args, **kwargs: next(answers),
    )
    monkeypatch.setattr(step, "_print_status_table", lambda *_: None)

    result = step.run(context)

    assert result.success is False
    assert "At least one LLM provider must be configured" in result.error
    assert "openai" not in context.configured_providers


def test_agent_step_deep_subtarget_runs_without_confirmation(monkeypatch):
    step = AgentSetupStep()
    context = _build_context()
    called = {"deep": False}

    def _run_deep(_context, _configured_items):
        called["deep"] = True

    def _unexpected_prompt(*args, **kwargs):
        raise AssertionError("Prompt.ask should not be called for sub_target='deep'")

    monkeypatch.setattr(step, "_run_deep", _run_deep)
    monkeypatch.setattr("src.core.config.setup.steps.agent.Prompt.ask", _unexpected_prompt)

    result = step.run(context, sub_target="deep")

    assert result.success is True
    assert called["deep"] is True


def test_setup_command_rejects_invalid_subtargets():
    command = SetupCommand()
    ctx = MagicMock()
    ctx.current_engine = "agent"
    ctx.console = MagicMock()

    invalid_agent = asyncio.run(command.execute(ctx, "--agent invalid"))
    assert invalid_agent.type == "error"
    assert "--agent" in invalid_agent.message

    invalid_tools = asyncio.run(command.execute(ctx, "--tools invalid"))
    assert invalid_tools.type == "error"
    assert "--tools" in invalid_tools.message


def test_setup_command_rejects_unknown_flag():
    command = SetupCommand()
    ctx = MagicMock()
    ctx.current_engine = "agent"
    ctx.console = MagicMock()

    result = asyncio.run(command.execute(ctx, "--unknown"))
    assert result.type == "error"
    assert "Unknown flag" in result.message

