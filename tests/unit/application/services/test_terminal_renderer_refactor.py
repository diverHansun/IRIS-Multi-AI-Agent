from __future__ import annotations

from typing import Any, AsyncGenerator
from unittest.mock import MagicMock

import pytest

from src.application.cli.renderers import (
    BasicTranscriptRenderer,
    DeepTranscriptRenderer,
    LLMTranscriptRenderer,
    SpinnerState,
    SpinnerStatusController,
)
from src.application.services.dify.streaming import DifyStreaming
from src.llm.utils.streaming import StreamingManager


def test_basic_transcript_renderer_renders_answer_and_tool_summary() -> None:
    console = MagicMock()
    renderer = BasicTranscriptRenderer(console)

    renderer.emit_assistant_text("done")
    renderer.emit_summary({"tool_calls": 2, "tool_names": ["shell", "web_search"]})

    printed = [str(call.args[0]) for call in console.print.call_args_list]
    assert any("BasicAgent >" in line for line in printed)
    assert any("Used 2 tools (2 calls): shell, web_search" in line for line in printed)


def test_llm_transcript_renderer_streams_chunks_with_single_prefix() -> None:
    console = MagicMock()
    renderer = LLMTranscriptRenderer(console)

    renderer.stream_chunk("Hel")
    renderer.stream_chunk("lo")
    renderer.finish_stream()

    assert console.print.call_count == 3
    first_call = console.print.call_args_list[0]
    second_call = console.print.call_args_list[1]
    third_call = console.print.call_args_list[2]
    assert "LLM >" in str(first_call.args[0])
    assert second_call.args[0] == "lo"
    assert third_call.args == ()


def test_spinner_state_exposes_semantic_subagent_label() -> None:
    state = SpinnerState.subagent_running("coding")

    assert state.visible is True
    assert state.label == "Subagent coding running..."


def test_spinner_status_controller_emits_state_transitions() -> None:
    captured: list[SpinnerState] = []
    controller = SpinnerStatusController(on_change=captured.append)

    controller.set_subagent_running("research")
    controller.set_idle()

    assert captured == [
        SpinnerState.subagent_running("research"),
        SpinnerState.idle(),
    ]


def test_deep_transcript_renderer_keeps_intermediate_text_primary() -> None:
    console = MagicMock()
    renderer = DeepTranscriptRenderer(console)

    renderer.emit_assistant_text("intermediate text", intermediate=True)

    rendered = console.print.call_args.args[0]
    styles = [span.style for span in rendered.spans]
    assert "dim" not in styles


def test_deep_transcript_renderer_renders_todo_updates_as_status_list() -> None:
    console = MagicMock()
    renderer = DeepTranscriptRenderer(console)

    renderer.emit_todo_update(
        [
            {"content": "Plan the research strategy", "status": "in_progress"},
            {"content": "Check Southeast University", "status": "pending"},
            {"content": "Summarize campus findings", "status": "completed"},
        ]
    )

    printed = [str(call.args[0]) for call in console.print.call_args_list if call.args]
    assert any("Tool: Todos updated" in line for line in printed)
    assert any("[..] Plan the research strategy" in line for line in printed)
    assert any("[ ] Check Southeast University" in line for line in printed)
    assert any("[OK] Summarize campus findings" in line for line in printed)


class _StreamingLLMStub:
    async def stream_generate(self, prompt: str) -> AsyncGenerator[str, None]:  # noqa: ARG002
        for chunk in ("Hel", "lo"):
            yield chunk


@pytest.mark.asyncio
async def test_streaming_manager_uses_renderer_path_for_llm_streams() -> None:
    manager = StreamingManager()
    manager.streaming_llms["mock"] = _StreamingLLMStub()
    renderer = MagicMock()

    result = await manager.stream_chat(
        provider="mock",
        prompt="hello",
        show_display=True,
        renderer=renderer,
    )

    assert result["response"] == "Hello"
    renderer.start_spinner.assert_called_once()
    assert renderer.stream_chunk.call_count == 2
    renderer.finish_stream.assert_called_once()


async def _dify_stream() -> AsyncGenerator[dict[str, Any], None]:
    yield {
        "event": "message",
        "answer": "Hello",
        "message_id": "msg-1",
        "conversation_id": "conv-1",
    }
    yield {
        "event": "message_end",
        "answer": "",
        "message_id": "msg-1",
        "conversation_id": "conv-1",
        "metadata": {"usage": {"tokens": 42}},
    }


@pytest.mark.asyncio
async def test_dify_streaming_uses_renderer_when_available() -> None:
    console = MagicMock()
    renderer = MagicMock()
    streaming = DifyStreaming(console, renderer=renderer)

    conversation_id = await streaming.display_stream(_dify_stream())

    assert conversation_id == "conv-1"
    renderer.start_spinner.assert_called_once()
    renderer.stop_spinner.assert_called()
    renderer.stream_chunk.assert_called_once_with("Hello")
    renderer.finish_stream.assert_called_once()
    renderer.emit.assert_called()
    body_prints = [call for call in console.print.call_args_list if call.args]
    assert not any("Hello" in str(call.args[0]) for call in body_prints)


