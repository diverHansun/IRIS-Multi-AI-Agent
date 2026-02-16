"""Unit tests for SubAgent state sharing implementation.

Tests verify that virtual filesystem state is correctly shared between
main agent and subagents through state copying and merging mechanisms.

Following testing principles:
- Each test has a single, clear purpose (SRP)
- Tests are independent and can run in any order
- Uses mocks to isolate units under test (DIP)
"""

import pytest
from unittest.mock import Mock, MagicMock
from src.components.deepagents.runtime_middlewares.subagents.middleware import (
    _prepare_subagent_state,
    _return_state_update,
    _EXCLUDED_STATE_KEYS,
)
from src.components.deepagents.runtime_middlewares.virtual_filesystem.types import FileData


class TestExcludedStateKeys:
    """Test excluded state keys configuration."""

    def test_excluded_keys_definition(self):
        """Verify excluded keys are correctly defined."""
        assert "messages" in _EXCLUDED_STATE_KEYS
        assert "todos" in _EXCLUDED_STATE_KEYS
        assert "_session_ctx" in _EXCLUDED_STATE_KEYS
        assert "_memory_sync" in _EXCLUDED_STATE_KEYS
        assert "_runtime_checkpointer" in _EXCLUDED_STATE_KEYS
        assert "_runtime_config" in _EXCLUDED_STATE_KEYS

    def test_files_not_excluded(self):
        """Verify that 'files' key is NOT excluded (critical for sharing)."""
        assert "files" not in _EXCLUDED_STATE_KEYS


class TestPrepareSubagentState:
    """Test state preparation function."""

    def test_excludes_messages_and_todos(self):
        """Verify messages and todos are excluded from subagent state."""
        # Setup
        runtime = Mock()
        runtime.state = {
            "messages": ["msg1", "msg2"],
            "todos": ["todo1", "todo2"],
            "files": {},
            "custom_key": "value"
        }
        description = "Test task"

        # Execute
        result = _prepare_subagent_state(runtime, description)

        # Verify
        assert "messages" in result  # New messages added
        assert result["messages"] == [{"role": "user", "content": description}]
        assert "todos" not in result  # Excluded
        assert "files" in result  # Included
        assert "custom_key" in result  # Other keys included

    def test_includes_files_state(self):
        """Verify files dictionary is copied to subagent state."""
        # Setup
        runtime = Mock()
        test_file = FileData(
            content=["test content"],
            created_at="2024-01-01T00:00:00",
            modified_at="2024-01-01T00:00:00"
        )
        runtime.state = {
            "messages": [],
            "files": {
                "/workspace/shared/test.txt": test_file
            }
        }
        description = "Read test.txt"

        # Execute
        result = _prepare_subagent_state(runtime, description)

        # Verify
        assert "files" in result
        assert "/workspace/shared/test.txt" in result["files"]
        assert result["files"]["/workspace/shared/test.txt"] == test_file

    def test_creates_new_messages_list(self):
        """Verify new messages list is created with task description."""
        # Setup
        runtime = Mock()
        runtime.state = {"messages": ["old message"]}
        description = "New task description"

        # Execute
        result = _prepare_subagent_state(runtime, description)

        # Verify
        assert result["messages"] == [{"role": "user", "content": description}]
        assert len(result["messages"]) == 1

    def test_handles_empty_state(self):
        """Verify function handles empty state gracefully."""
        # Setup
        runtime = Mock()
        runtime.state = {}
        description = "Task"

        # Execute
        result = _prepare_subagent_state(runtime, description)

        # Verify
        assert "messages" in result
        assert result["messages"] == [{"role": "user", "content": description}]


class TestReturnStateUpdate:
    """Test state update return function."""

    def test_excludes_messages_and_todos_from_update(self):
        """Verify messages and todos are excluded from state update."""
        # Setup
        result = {
            "messages": [Mock(content="Response")],
            "todos": ["new_todo"],
            "files": {"/file.txt": Mock()},
            "custom_state": "value"
        }
        tool_call_id = "test-call-id"

        # Execute
        command = _return_state_update(result, tool_call_id)

        # Verify
        assert hasattr(command, "update")
        update = command.update
        assert "messages" in update  # New ToolMessage added
        assert "todos" not in update  # Excluded from state update
        assert "files" in update  # Included in state update
        assert "custom_state" in update

    def test_includes_files_in_update(self):
        """Verify files dictionary is included in state update."""
        # Setup
        test_file = FileData(
            content=["result"],
            created_at="2024-01-01T00:00:00",
            modified_at="2024-01-01T00:00:00"
        )
        result = {
            "messages": [Mock(content="Done")],
            "files": {"/workspace/shared/result.txt": test_file}
        }
        tool_call_id = "test-id"

        # Execute
        command = _return_state_update(result, tool_call_id)

        # Verify
        update = command.update
        assert "files" in update
        assert "/workspace/shared/result.txt" in update["files"]

    def test_creates_tool_message_with_response(self):
        """Verify ToolMessage is created with correct content and ID."""
        # Setup
        response_content = "Task completed successfully"
        result = {
            "messages": [Mock(content=response_content)]
        }
        tool_call_id = "test-call-id-123"

        # Execute
        command = _return_state_update(result, tool_call_id)

        # Verify
        update = command.update
        assert "messages" in update
        assert len(update["messages"]) == 1
        message = update["messages"][0]
        assert message["role"] == "tool"
        assert message["content"] == response_content
        assert message["tool_call_id"] == tool_call_id

    def test_handles_empty_messages(self):
        """Verify function handles empty messages list gracefully."""
        # Setup
        result = {"messages": []}
        tool_call_id = "test-id"

        # Execute
        command = _return_state_update(result, tool_call_id)

        # Verify
        update = command.update
        assert "messages" in update
        assert update["messages"][0]["content"] == ""

    def test_handles_message_without_content_attr(self):
        """Verify function handles messages without content attribute."""
        # Setup: Create object without content attribute
        class MessageWithoutContent:
            def __str__(self):
                return "String representation"

        result = {"messages": [MessageWithoutContent()]}
        tool_call_id = "test-id"

        # Execute
        command = _return_state_update(result, tool_call_id)

        # Verify
        update = command.update
        assert "messages" in update
        # Should fallback to str() representation
        assert update["messages"][0]["content"] == "String representation"


class TestStateSharing:
    """Integration tests for state sharing flow."""

    def test_complete_state_sharing_flow(self):
        """Test complete flow: prepare -> execute -> return."""
        # Setup: Main agent state
        main_agent_file = FileData(
            content=["input data"],
            created_at="2024-01-01T00:00:00",
            modified_at="2024-01-01T00:00:00"
        )
        runtime = Mock()
        runtime.state = {
            "messages": ["main agent message"],
            "todos": ["main todo"],
            "files": {"/workspace/shared/input.txt": main_agent_file}
        }
        description = "Process input.txt"

        # Step 1: Prepare subagent state
        subagent_state = _prepare_subagent_state(runtime, description)

        # Verify subagent receives files but not messages/todos
        assert "files" in subagent_state
        assert "/workspace/shared/input.txt" in subagent_state["files"]
        assert "todos" not in subagent_state
        assert subagent_state["messages"] == [{"role": "user", "content": description}]

        # Step 2: Simulate subagent execution and file creation
        subagent_result_file = FileData(
            content=["processed data"],
            created_at="2024-01-01T01:00:00",
            modified_at="2024-01-01T01:00:00"
        )
        subagent_result = {
            "messages": [Mock(content="Processing complete")],
            "todos": ["subagent todo"],
            "files": {
                "/workspace/shared/input.txt": main_agent_file,
                "/workspace/shared/output.txt": subagent_result_file
            }
        }

        # Step 3: Return state update
        command = _return_state_update(subagent_result, "test-call-id")

        # Verify state update includes files
        update = command.update
        assert "files" in update
        assert "/workspace/shared/output.txt" in update["files"]
        assert "todos" not in update
        assert "messages" in update
        assert update["messages"][0]["content"] == "Processing complete"


class TestFileDataReducerIntegration:
    """Test integration with FilesystemState reducer."""

    def test_files_state_structure(self):
        """Verify files state structure is compatible with reducer."""
        from src.components.deepagents.runtime_middlewares.virtual_filesystem.types import (
            _file_data_reducer,
        )

        # Setup: Initial state
        current = {
            "/file1.txt": FileData(
                content=["line1"],
                created_at="2024-01-01T00:00:00",
                modified_at="2024-01-01T00:00:00"
            )
        }

        # Setup: Updates from subagent
        updates = {
            "/file1.txt": FileData(
                content=["line1", "line2"],
                created_at="2024-01-01T00:00:00",
                modified_at="2024-01-02T00:00:00"
            ),
            "/file2.txt": FileData(
                content=["new file"],
                created_at="2024-01-02T00:00:00",
                modified_at="2024-01-02T00:00:00"
            )
        }

        # Execute: Merge using reducer
        merged = _file_data_reducer(current, updates)

        # Verify: Reducer correctly merges files
        assert "/file1.txt" in merged
        assert len(merged["/file1.txt"]["content"]) == 2
        assert "/file2.txt" in merged
        assert merged["/file2.txt"]["content"] == ["new file"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
