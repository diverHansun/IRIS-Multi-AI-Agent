"""Unit tests for PatchToolCallsMiddleware."""

import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from src.components.deepagents.runtime_middlewares import PatchToolCallsMiddleware


class TestPatchToolCallsMiddleware:
    """Test suite for PatchToolCallsMiddleware."""

    def setup_method(self):
        """Set up test fixtures."""
        self.middleware = PatchToolCallsMiddleware()

    def create_mock_state(self, messages):
        """Create a mock AgentState with given messages."""
        return {"messages": messages}

    def create_mock_runtime(self):
        """Create a mock Runtime object."""
        return MagicMock()

    def test_empty_messages_returns_none(self):
        """Test that empty messages list returns None."""
        state = self.create_mock_state([])
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is None

    def test_none_messages_returns_none(self):
        """Test that None messages returns None."""
        state = {"messages": None}
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is None

    def test_no_tool_calls_returns_none(self):
        """Test that messages without tool calls returns None (early exit optimization)."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is None

    def test_all_tool_calls_matched_returns_none(self):
        """Test that when all tool calls have corresponding responses, returns None (early exit)."""
        messages = [
            HumanMessage(content="Search for something"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search", "args": {"query": "test"}, "id": "call_123"}
                ]
            ),
            ToolMessage(
                content="Search results",
                tool_call_id="call_123",
                name="search"
            ),
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is None

    def test_single_dangling_tool_call_gets_patched(self):
        """Test that a single dangling tool call gets patched correctly."""
        messages = [
            HumanMessage(content="Search for something"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search", "args": {"query": "test"}, "id": "call_123"}
                ]
            ),
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is not None
        assert "messages" in result

        # Should have RemoveMessage + original messages + patched ToolMessage
        result_messages = result["messages"]
        assert len(result_messages) == 4  # RemoveMessage + 2 original + 1 patched

        # First message should be RemoveMessage
        assert isinstance(result_messages[0], RemoveMessage)
        assert result_messages[0].id == REMOVE_ALL_MESSAGES

        # Last message should be the patched ToolMessage
        patched_msg = result_messages[-1]
        assert isinstance(patched_msg, ToolMessage)
        assert patched_msg.tool_call_id == "call_123"
        assert patched_msg.name == "search"
        assert "call_123" in patched_msg.content
        assert "cancelled before completion" in patched_msg.content

    def test_multiple_dangling_tool_calls_get_patched(self):
        """Test that multiple dangling tool calls all get patched."""
        messages = [
            HumanMessage(content="Do multiple things"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search", "args": {"query": "test1"}, "id": "call_1"},
                    {"name": "calculator", "args": {"expr": "2+2"}, "id": "call_2"},
                ]
            ),
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is not None
        result_messages = result["messages"]

        # RemoveMessage + 2 original + 2 patched ToolMessages
        assert len(result_messages) == 5

        # Check both patched tool messages
        patched_msgs = [msg for msg in result_messages if isinstance(msg, ToolMessage)]
        assert len(patched_msgs) == 2

        tool_call_ids = {msg.tool_call_id for msg in patched_msgs}
        assert tool_call_ids == {"call_1", "call_2"}

    def test_mixed_matched_and_dangling_tool_calls(self):
        """Test scenario with both matched and dangling tool calls."""
        messages = [
            HumanMessage(content="Do multiple things"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search", "args": {"query": "test1"}, "id": "call_1"},
                    {"name": "calculator", "args": {"expr": "2+2"}, "id": "call_2"},
                ]
            ),
            ToolMessage(content="4", tool_call_id="call_2", name="calculator"),
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is not None
        result_messages = result["messages"]

        # RemoveMessage + 3 original + 1 patched ToolMessage (only call_1 is dangling)
        assert len(result_messages) == 5

        # Check that only the dangling tool call was patched
        patched_msgs = [
            msg for msg in result_messages
            if isinstance(msg, ToolMessage) and "cancelled before completion" in msg.content
        ]
        assert len(patched_msgs) == 1
        assert patched_msgs[0].tool_call_id == "call_1"

    def test_ai_message_with_empty_tool_calls_list(self):
        """Test AI message with empty tool_calls list (edge case)."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi", tool_calls=[]),
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        # Should return None (no dangling calls)
        assert result is None

    def test_multiple_ai_messages_with_tool_calls(self):
        """Test multiple AI messages, some with dangling tool calls."""
        messages = [
            HumanMessage(content="First request"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search", "args": {"query": "test1"}, "id": "call_1"}
                ]
            ),
            ToolMessage(content="Result 1", tool_call_id="call_1", name="search"),
            HumanMessage(content="Second request"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "calculator", "args": {"expr": "5+5"}, "id": "call_2"}
                ]
            ),
            # call_2 has no response - dangling
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is not None
        result_messages = result["messages"]

        # Check that only call_2 was patched
        patched_msgs = [
            msg for msg in result_messages
            if isinstance(msg, ToolMessage) and "cancelled before completion" in msg.content
        ]
        assert len(patched_msgs) == 1
        assert patched_msgs[0].tool_call_id == "call_2"

    def test_preserves_message_order(self):
        """Test that message order is preserved during patching."""
        messages = [
            HumanMessage(content="Request 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Request 2"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search", "args": {"query": "test"}, "id": "call_1"}
                ]
            ),
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is not None
        result_messages = result["messages"]

        # Skip RemoveMessage for order comparison
        actual_messages = result_messages[1:]

        # First 4 messages should be original messages in order
        assert len(actual_messages) >= 4
        assert isinstance(actual_messages[0], HumanMessage)
        assert actual_messages[0].content == "Request 1"
        assert isinstance(actual_messages[1], AIMessage)
        assert actual_messages[1].content == "Response 1"
        assert isinstance(actual_messages[2], HumanMessage)
        assert actual_messages[2].content == "Request 2"
        assert isinstance(actual_messages[3], AIMessage)

        # Last message should be patched ToolMessage
        assert isinstance(actual_messages[4], ToolMessage)
        assert actual_messages[4].tool_call_id == "call_1"

    def test_single_message_no_tool_calls(self):
        """Test with single message that has no tool calls."""
        messages = [HumanMessage(content="Hello")]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is None

    def test_tool_call_id_matching_is_exact(self):
        """Test that tool call ID matching is exact (not partial)."""
        messages = [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search", "args": {"query": "test"}, "id": "call_123"}
                ]
            ),
            ToolMessage(
                content="Wrong call",
                tool_call_id="call_456",  # Different ID
                name="search"
            ),
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        assert result is not None

        # call_123 should be patched since call_456 doesn't match
        patched_msgs = [
            msg for msg in result["messages"]
            if isinstance(msg, ToolMessage) and msg.tool_call_id == "call_123"
        ]
        assert len(patched_msgs) == 1

    def test_patched_message_format(self):
        """Test that patched ToolMessage has correct format."""
        messages = [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "my_tool", "args": {"param": "value"}, "id": "call_xyz"}
                ]
            ),
        ]
        state = self.create_mock_state(messages)
        runtime = self.create_mock_runtime()

        result = self.middleware.before_agent(state, runtime)

        patched_msg = result["messages"][-1]

        assert isinstance(patched_msg, ToolMessage)
        assert patched_msg.tool_call_id == "call_xyz"
        assert patched_msg.name == "my_tool"
        assert "my_tool" in patched_msg.content
        assert "call_xyz" in patched_msg.content
        assert "cancelled before completion" in patched_msg.content
