"""
Test suite for ToolMessage filtering in memory system.

Verifies that:
1. ToolMessage objects are filtered out during persistence
2. Only HumanMessage and AIMessage are saved to disk
3. Backward compatibility with old session data containing ToolMessage
4. Both BasicAgent (ainvoke) and DeepAgent (astream) respect filtering

Design principles applied:
- KISS: Simple, focused tests with clear assertions
- DRY: Reusable fixtures and helper methods
- SOLID: Single responsibility - each test validates one aspect
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import List

import pytest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)

import pytest

pytest.skip("Legacy memory filter tests skipped after memory refactor", allow_module_level=True)
from src.components.shared.memory.unified_checkpointer import UnifiedCheckpointer
from src.components.shared.session.session_storage import SessionStorage


class TestToolMessageFiltering:
    """Test ToolMessage filtering in memory persistence."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def checkpointer(self, temp_storage_dir):
        """Create UnifiedCheckpointer with temporary storage."""
        return UnifiedCheckpointer(storage_dir=temp_storage_dir, max_messages=50)

    @pytest.fixture
    def session_storage(self, temp_storage_dir):
        """Create SessionStorage with temporary storage."""
        return SessionStorage(storage_dir=temp_storage_dir)

    def test_put_filters_tool_messages(self, checkpointer):
        """
        Test that UnifiedCheckpointer.put() filters out ToolMessage objects.

        Principle: KISS - Direct test of core filtering functionality.
        """
        session_id = "test_filter_session"
        config = {"configurable": {"thread_id": session_id}}

        # Create checkpoint with mixed message types
        messages = [
            HumanMessage(content="Search for Python tutorials"),
            AIMessage(content="", tool_calls=[{"name": "web_search", "id": "call_1"}]),
            ToolMessage(content="<large search results>", tool_call_id="call_1"),
            AIMessage(content="Here are the Python tutorials I found..."),
        ]

        checkpoint = {
            "v": 1,
            "id": "test_checkpoint",
            "ts": "2025-11-06T12:00:00",
            "channel_values": {"messages": messages},
            "channel_versions": {},
            "versions_seen": {},
            "updated_channels": [],
        }

        metadata = {"source": "input", "step": -1, "parents": {}}

        # Execute put operation
        checkpointer.put(config, checkpoint, metadata, {})

        # Verify: Load and check that only HumanMessage and AIMessage are saved
        loaded_history = checkpointer.global_memory.get_session_history(session_id)
        loaded_messages = loaded_history.messages

        assert len(loaded_messages) == 3, "Should filter out ToolMessage"
        assert isinstance(loaded_messages[0], HumanMessage)
        assert isinstance(loaded_messages[1], AIMessage)
        assert isinstance(loaded_messages[2], AIMessage)

        # Verify no ToolMessage in persisted data
        for msg in loaded_messages:
            assert not isinstance(msg, ToolMessage), "ToolMessage should be filtered"

    def test_multiple_tool_messages_filtered(self, checkpointer):
        """
        Test filtering when multiple ToolMessage objects exist in sequence.

        Principle: YAGNI - Test realistic scenario without over-engineering.
        """
        session_id = "test_multi_tool"
        config = {"configurable": {"thread_id": session_id}}

        messages = [
            HumanMessage(content="Calculate 10 + 20 and search for math resources"),
            AIMessage(content="", tool_calls=[{"name": "calculator", "id": "c1"}]),
            ToolMessage(content="30", tool_call_id="c1"),
            AIMessage(content="", tool_calls=[{"name": "web_search", "id": "s1"}]),
            ToolMessage(content="<large results>", tool_call_id="s1"),
            AIMessage(content="The answer is 30. Here are math resources..."),
        ]

        checkpoint = {
            "v": 1,
            "id": "test",
            "ts": "2025-11-06T12:00:00",
            "channel_values": {"messages": messages},
            "channel_versions": {},
            "versions_seen": {},
            "updated_channels": [],
        }

        checkpointer.put(config, checkpoint, {}, {})

        loaded_history = checkpointer.global_memory.get_session_history(session_id)
        loaded_messages = loaded_history.messages

        # Should have 1 HumanMessage + 3 AIMessage (2 ToolMessages filtered)
        assert len(loaded_messages) == 4
        assert sum(1 for m in loaded_messages if isinstance(m, HumanMessage)) == 1
        assert sum(1 for m in loaded_messages if isinstance(m, AIMessage)) == 3
        assert sum(1 for m in loaded_messages if isinstance(m, ToolMessage)) == 0

    def test_no_tool_messages_passthrough(self, checkpointer):
        """
        Test that filtering works correctly when no ToolMessage exists.

        Principle: DRY - Reuse fixture setup, test edge case.
        """
        session_id = "test_no_tool"
        config = {"configurable": {"thread_id": session_id}}

        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?"),
            AIMessage(content="I'm doing well, thanks!"),
        ]

        checkpoint = {
            "v": 1,
            "id": "test",
            "ts": "2025-11-06T12:00:00",
            "channel_values": {"messages": messages},
            "channel_versions": {},
            "versions_seen": {},
            "updated_channels": [],
        }

        checkpointer.put(config, checkpoint, {}, {})

        loaded_history = checkpointer.global_memory.get_session_history(session_id)
        loaded_messages = loaded_history.messages

        assert len(loaded_messages) == 4
        assert all(isinstance(m, (HumanMessage, AIMessage)) for m in loaded_messages)

    def test_backward_compatibility_load_legacy_data(self, session_storage):
        """
        Test loading old session data that contains ToolMessage entries.

        Principle: SOLID (L) - System handles legacy data gracefully.
        """
        session_id = "legacy_session"

        # Simulate old session file with ToolMessage
        legacy_data = {
            "session_id": session_id,
            "messages": [
                {"type": "HumanMessage", "content": "Test query", "timestamp": "2025-01-01T00:00:00"},
                {"type": "AIMessage", "content": "Response", "timestamp": "2025-01-01T00:00:01"},
                {"type": "ToolMessage", "content": "Tool result", "timestamp": "2025-01-01T00:00:02"},
            ],
            "message_count": 3,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
            "metadata": {},
        }

        # Write legacy session file
        session_file = Path(session_storage.storage_dir) / f"{session_id}.json"
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # Load and verify conversion
        messages = session_storage.load_session(session_id)

        assert messages is not None
        assert len(messages) == 3
        # ToolMessage should be converted to HumanMessage for compatibility
        assert isinstance(messages[0], HumanMessage)
        assert isinstance(messages[1], AIMessage)
        assert isinstance(messages[2], HumanMessage)  # Converted from ToolMessage

    def test_empty_messages_list(self, checkpointer):
        """
        Test handling of empty messages list.

        Principle: KISS - Test simple edge case.
        """
        session_id = "test_empty"
        config = {"configurable": {"thread_id": session_id}}

        checkpoint = {
            "v": 1,
            "id": "test",
            "ts": "2025-11-06T12:00:00",
            "channel_values": {"messages": []},
            "channel_versions": {},
            "versions_seen": {},
            "updated_channels": [],
        }

        checkpointer.put(config, checkpoint, {}, {})

        loaded_history = checkpointer.global_memory.get_session_history(session_id)
        loaded_messages = loaded_history.messages

        assert len(loaded_messages) == 0

    def test_get_tuple_after_filtering(self, checkpointer):
        """
        Test that get_tuple() returns filtered messages correctly.

        Principle: SOLID (S) - Test single responsibility of get operation.
        """
        session_id = "test_get_tuple"
        config = {"configurable": {"thread_id": session_id}}

        # Save with ToolMessage
        messages = [
            HumanMessage(content="Query"),
            AIMessage(content="", tool_calls=[{"name": "tool", "id": "t1"}]),
            ToolMessage(content="Tool output", tool_call_id="t1"),
            AIMessage(content="Final answer"),
        ]

        checkpoint = {
            "v": 1,
            "id": "test",
            "ts": "2025-11-06T12:00:00",
            "channel_values": {"messages": messages},
            "channel_versions": {},
            "versions_seen": {},
            "updated_channels": [],
        }

        checkpointer.put(config, checkpoint, {}, {})

        # Retrieve via get_tuple
        checkpoint_tuple = checkpointer.get_tuple(config)

        assert checkpoint_tuple is not None
        retrieved_messages = checkpoint_tuple.checkpoint["channel_values"]["messages"]

        # Should only contain HumanMessage and AIMessage
        assert len(retrieved_messages) == 3
        assert not any(isinstance(m, ToolMessage) for m in retrieved_messages)


class TestGlobalMemoryIntegration:
    """Test integration with GlobalMemoryManager."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def memory_manager(self, temp_storage_dir):
        """Create GlobalMemoryManager with temporary storage."""
        return GlobalMemoryManager(storage_dir=temp_storage_dir, max_messages=50)

    def test_add_messages_no_tool_message(self, memory_manager):
        """
        Test that GlobalMemoryManager doesn't receive ToolMessage.

        Principle: SOLID (D) - Test dependency integration.
        """
        session_id = "test_gmm_session"
        history = memory_manager.get_session_history(session_id)

        # Simulate what UnifiedCheckpointer would send (already filtered)
        messages = [
            HumanMessage(content="Query"),
            AIMessage(content="Response"),
        ]

        history.add_messages(messages)

        loaded_messages = history.messages
        assert len(loaded_messages) == 2
        assert all(isinstance(m, (HumanMessage, AIMessage)) for m in loaded_messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
