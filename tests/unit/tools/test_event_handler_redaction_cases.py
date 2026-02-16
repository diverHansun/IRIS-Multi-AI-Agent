"""Tests for deep streaming tool-result redaction in CLI updates."""

from __future__ import annotations

from unittest.mock import Mock

from langchain_core.messages import ToolMessage

from src.application.services.agent.deep.streaming.event_handler import DeepAgentEventHandler


class _DummyConsole:
    def print(self, *args, **kwargs):  # pragma: no cover - test helper
        return None


def test_describe_messages_hides_tool_result_content_success() -> None:
    handler = DeepAgentEventHandler(_DummyConsole())
    tool_msg = Mock(spec=ToolMessage)
    tool_msg.name = "read_real_file"
    tool_msg.status = "success"
    tool_msg.content = "SECRET FILE CONTENT"

    description = handler._describe_messages("tools", [tool_msg])

    assert description == "tools: Tool 'read_real_file' completed."
    assert "SECRET FILE CONTENT" not in description


def test_describe_messages_hides_tool_result_content_failure() -> None:
    handler = DeepAgentEventHandler(_DummyConsole())
    tool_msg = Mock(spec=ToolMessage)
    tool_msg.name = "execute_shell"
    tool_msg.status = "error"
    tool_msg.content = "very long stack trace"

    description = handler._describe_messages("tools", [tool_msg])

    assert description == "tools: Tool 'execute_shell' failed."
    assert "stack trace" not in description
