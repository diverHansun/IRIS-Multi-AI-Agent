"""Tests for timeout recovery and message filtering behavior."""

import os
import sys

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../..", "src"))

from components.shared.storage.message_filter import MessageFilter


def test_system_notification_detection():
    """System notifications should be detected by message type."""
    message_filter = MessageFilter()

    system_notifications = [
        SystemMessage(content="SYSTEM NOTIFICATION: timeout"),
        ToolMessage(content="tool output", tool_call_id="call-1"),
    ]
    for message in system_notifications:
        assert message_filter.is_system_notification(message)

    normal_messages = [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi"),
    ]
    for message in normal_messages:
        assert not message_filter.is_system_notification(message)


def test_system_notification_filtering():
    """System notifications should be removed from persisted history."""
    message_filter = MessageFilter()

    messages = [
        HumanMessage(content="Original query about Chinese students"),
        SystemMessage(content="SYSTEM NOTIFICATION: timeout"),
        HumanMessage(content="Continue the task"),
        AIMessage(content="Continuing with the task..."),
        SystemMessage(content="[User interrupted the previous request with Ctrl+C]"),
        HumanMessage(content="Try again"),
        AIMessage(content="Trying again..."),
    ]

    filtered = message_filter.filter_message_history(messages)
    assert len(filtered) == 5
    assert all(not isinstance(msg, (SystemMessage, ToolMessage)) for msg in filtered)

    filtered_contents = [msg.content for msg in filtered]
    assert "Original query about Chinese students" in filtered_contents
    assert "Continue the task" in filtered_contents
    assert "Continuing with the task..." in filtered_contents
    assert "Try again" in filtered_contents
    assert "Trying again..." in filtered_contents


def test_timeout_message_format():
    """Timeout handling should notify the runtime using SystemMessage."""
    conv_file = "src/application/services/agent/deep/streaming/conversation.py"
    with open(conv_file, "r", encoding="utf-8") as stream:
        content = stream.read()

    assert "except TimeoutError" in content
    assert "aupdate_state" in content
    assert "SystemMessage" in content
    assert "SYSTEM NOTIFICATION: The previous operation timed out" in content


def test_filter_integration():
    """Timeout notification should not pollute persisted conversation."""
    message_filter = MessageFilter()

    messages = [
        HumanMessage(content="Go research recent events about Chinese students"),
        SystemMessage(content="SYSTEM NOTIFICATION: timeout"),
        HumanMessage(content="continue"),
        AIMessage(content="I understand the timeout occurred. Let me retry the research task..."),
    ]

    filtered = message_filter.filter_message_history(messages)
    assert len(filtered) == 3
    contents = [msg.content for msg in filtered]

    assert "Go research recent events about Chinese students" in contents
    assert "continue" in contents
    assert any("retry the research task" in str(c) for c in contents)
    assert not any("SYSTEM NOTIFICATION" in str(c) for c in contents)


def test_official_pattern_consistency():
    """
    Compare with official pattern when vendor source is available locally.

    The local repository may not vendor deepagents-cli source.
    """
    official_file = "deepagents/libs/deepagents-cli/deepagents_cli/execution.py"
    if not os.path.exists(official_file):
        pytest.skip("official deepagents-cli source not vendored in this repository")

    with open(official_file, "r", encoding="utf-8") as stream:
        official_content = stream.read()

    assert "HumanMessage" in official_content or "SystemMessage" in official_content

    our_file = "src/application/services/agent/deep/streaming/conversation.py"
    with open(our_file, "r", encoding="utf-8") as stream:
        our_content = stream.read()

    assert "aupdate_state" in our_content
    assert "SYSTEM NOTIFICATION: The previous operation timed out" in our_content
