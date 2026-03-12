"""Unit tests for dual-mode streaming implementation."""

import json
import unittest
from unittest.mock import MagicMock, Mock

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import Interrupt

from src.application.services.agent.deep.streaming.event_handler import (
    DeepAgentEventHandler,
    EventProcessingResult,
)
from src.application.services.agent.deep.hitl.file_ops import (
    FileOpTracker,
)


class TestFileOpTracker(unittest.TestCase):
    """Test FileOpTracker functionality."""

    def setUp(self):
        self.tracker = FileOpTracker()

    def test_start_operation_file_tools(self):
        """Test starting file operation tracking."""
        self.tracker.start_operation(
            "write_real_file", {"file_path": "test.py", "content": "data"}, "call-123"
        )

        self.assertIn("call-123", self.tracker.active)
        record = self.tracker.active["call-123"]
        self.assertEqual(record.tool_name, "write_real_file")
        self.assertEqual(record.tool_call_id, "call-123")
        self.assertEqual(record.status, "pending")

    def test_start_operation_non_file_tools(self):
        """Test that non-file tools are ignored."""
        self.tracker.start_operation("web_search", {"query": "test"}, "call-456")

        self.assertEqual(len(self.tracker.active), 0)

    def test_complete_with_message_success(self):
        """Test completing operation with success message."""
        self.tracker.start_operation(
            "bash", {"command": "echo hello"}, "call-123"
        )

        tool_msg = Mock(spec=ToolMessage)
        tool_msg.tool_call_id = "call-123"
        tool_msg.content = "hello"
        tool_msg.status = "success"

        record = self.tracker.complete_with_message(tool_msg)

        self.assertIsNotNone(record)
        self.assertEqual(record.status, "success")
        self.assertNotIn("call-123", self.tracker.active)
        self.assertEqual(len(self.tracker.completed), 1)

    def test_complete_with_message_error(self):
        """Test completing operation with error message."""
        self.tracker.start_operation(
            "bash", {"command": "rm -rf /tmp/demo"}, "call-789"
        )

        tool_msg = Mock(spec=ToolMessage)
        tool_msg.tool_call_id = "call-789"
        tool_msg.content = "Error: permission denied"
        tool_msg.status = "error"

        record = self.tracker.complete_with_message(tool_msg)

        self.assertIsNotNone(record)
        self.assertEqual(record.status, "error")
        self.assertEqual(record.error, "Error: permission denied")

    def test_complete_unknown_operation(self):
        """Test completing operation that was not tracked."""
        tool_msg = Mock(spec=ToolMessage)
        tool_msg.tool_call_id = "unknown-id"
        tool_msg.content = "result"

        record = self.tracker.complete_with_message(tool_msg)

        self.assertIsNone(record)


class TestEventHandlerDualMode(unittest.TestCase):
    """Test DeepAgentEventHandler dual-mode streaming."""

    def setUp(self):
        self.console = MagicMock()
        self.handler = DeepAgentEventHandler(
            self.console,
            file_tracker=FileOpTracker(),
            show_reasoning_steps=True,
            show_tool_calls=True,
            show_tool_results=True,
        )

    def test_handle_tuple_format_messages_stream(self):
        """Test handling tuple format with messages stream."""
        message = AIMessage(content="Hello world")
        metadata = {}
        event = (("node1",), "messages", (message, metadata))

        result = self.handler.handle_event(event)

        self.assertIsInstance(result, EventProcessingResult)

    def test_handle_tuple_format_updates_stream(self):
        """Test handling tuple format with updates stream."""
        event = (("node1",), "updates", {"agent": {"messages": []}})

        result = self.handler.handle_event(event)

        self.assertIsInstance(result, EventProcessingResult)

    def test_handle_dict_format_backwards_compatibility(self):
        """Test handling dict format for backwards compatibility."""
        event = {"agent": {"messages": []}}

        result = self.handler.handle_event(event)

        self.assertIsInstance(result, EventProcessingResult)

    def test_handle_interrupt_in_updates(self):
        """Test interrupt handling in updates stream."""
        interrupt = Interrupt(value={"test": "data"})
        event = (("node1",), "updates", {"__interrupt__": (interrupt,)})

        result = self.handler.handle_event(event)

        self.assertEqual(len(result.interrupts), 1)

    def test_process_text_block(self):
        """Test processing text content blocks."""
        message = Mock(spec=AIMessage)
        message.content_blocks = [{"type": "text", "text": "Hello "}]

        self.handler._process_ai_message_content_blocks(message)

        self.assertEqual(self.handler._pending_text, "Hello ")

    def test_process_multiple_text_blocks(self):
        """Test accumulating multiple text blocks."""
        message1 = Mock(spec=AIMessage)
        message1.content_blocks = [{"type": "text", "text": "Hello "}]
        message1.chunk_position = None

        message2 = Mock(spec=AIMessage)
        message2.content_blocks = [{"type": "text", "text": "world"}]
        message2.chunk_position = None

        self.handler._process_ai_message_content_blocks(message1)
        self.handler._process_ai_message_content_blocks(message2)

        self.assertEqual(self.handler._pending_text, "Hello world")

    def test_process_tool_call_chunk_with_dict_args(self):
        """Test tool call chunk with complete dict args."""
        block = {
            "type": "tool_call_chunk",
            "index": 0,
            "name": "read_file",
            "id": "call-123",
            "args": {"file_path": "test.py"},
        }

        self.handler._handle_tool_call_chunk(block)

        self.assertIn("call-123", self.handler._displayed_tool_ids)
        self.assertEqual(len(self.handler._tool_call_buffers), 0)

    def test_process_tool_call_chunk_with_string_args(self):
        """Test tool call chunk with JSON string args."""
        block1 = {
            "type": "tool_call_chunk",
            "index": 0,
            "name": "read_file",
            "id": "call-456",
            "args": '{"file_path":',
        }

        self.handler._handle_tool_call_chunk(block1)

        self.assertEqual(len(self.handler._tool_call_buffers), 1)
        self.assertNotIn("call-456", self.handler._displayed_tool_ids)

        block2 = {
            "type": "tool_call_chunk",
            "index": 0,
            "args": ' "test.py"}',
        }

        self.handler._handle_tool_call_chunk(block2)

        self.assertIn("call-456", self.handler._displayed_tool_ids)
        self.assertEqual(len(self.handler._tool_call_buffers), 0)

    def test_process_tool_call_chunk_invalid_json(self):
        """Test tool call chunk with invalid JSON waits for more chunks."""
        block = {
            "type": "tool_call_chunk",
            "index": 0,
            "name": "read_file",
            "id": "call-789",
            "args": '{"file_path"',
        }

        self.handler._handle_tool_call_chunk(block)

        self.assertEqual(len(self.handler._tool_call_buffers), 1)
        self.assertNotIn("call-789", self.handler._displayed_tool_ids)

    def test_process_tool_message_success(self):
        """Test processing successful tool message."""
        tool_msg = Mock(spec=ToolMessage)
        tool_msg.name = "bash"
        tool_msg.status = "success"
        tool_msg.content = "done"
        tool_msg.tool_call_id = "call-123"

        self.handler._file_tracker.start_operation(
            "bash", {"command": "echo done"}, "call-123"
        )

        self.handler._process_tool_message(tool_msg)

        self.assertEqual(len(self.handler._file_tracker.completed), 1)

    def test_process_tool_message_error(self):
        """Test processing error tool message displays error."""
        tool_msg = Mock(spec=ToolMessage)
        tool_msg.name = "shell"
        tool_msg.status = "error"
        tool_msg.content = "Error: Command failed"
        tool_msg.tool_call_id = "call-456"

        self.handler._process_tool_message(tool_msg)

        self.console.print.assert_called()

    def test_flush_text_buffer_only_on_final(self):
        """Test text buffer flushes only when final=True."""
        self.handler._pending_text = "test text"

        self.handler._flush_text_buffer(final=False)
        self.assertEqual(self.handler._pending_text, "test text")

        self.handler._flush_text_buffer(final=True)
        self.assertEqual(self.handler._pending_text, "")
        self.console.print.assert_called()
        self.assertTrue(self.handler.has_streamed_answer("test text"))

    def test_chunk_position_last_flushes_buffer(self):
        """Test that chunk_position=last flushes text buffer."""
        message = Mock(spec=AIMessageChunk)
        message.content_blocks = [{"type": "text", "text": "final text"}]
        message.chunk_position = "last"

        self.handler._process_ai_message_content_blocks(message)

        self.assertEqual(self.handler._pending_text, "")
        self.assertTrue(self.handler.has_streamed_answer("final text"))

    def test_describe_messages_uses_thinking_for_plain_text_ai(self):
        """Test Step rows no longer leak AI text content."""
        message = AIMessage(content="This should not appear in the Step row")

        description = self.handler._describe_messages("model", [message])

        self.assertEqual(description, "model: Thinking")

    def test_describe_messages_uses_thinking_when_tool_calls_hidden(self):
        """Test tool-call updates still render a status when tool display is disabled."""
        self.handler.show_tool_calls = False
        message = AIMessage(
            content="",
            tool_calls=[
                {"name": "web_search", "args": {"query": "demo"}, "id": "call-1"}
            ],
        )

        description = self.handler._describe_messages("model", [message])

        self.assertEqual(description, "model: Thinking")

    def test_direct_tool_call_flush_does_not_mark_final_answer_streamed(self):
        """Test direct tool calls flush pending text as intermediate output."""
        self.handler._pending_text = "Let me search first"

        self.handler._process_direct_tool_call(
            {"name": "web_search", "args": {"query": "demo"}, "id": "call-1"}
        )

        self.assertEqual(self.handler._pending_text, "")
        self.assertFalse(self.handler.has_streamed_answer("Let me search first"))

    def test_message_end_after_direct_tool_call_does_not_override_intermediate_flush(self):
        """Test message_end runs after direct tool handling without misclassifying text."""
        message = Mock(spec=AIMessageChunk)
        message.content_blocks = [{"type": "text", "text": "Need to inspect this"}]
        message.tool_calls = [
            {"name": "web_search", "args": {"query": "demo"}, "id": "call-2"}
        ]
        message.chunk_position = "last"

        self.handler._process_ai_message_content_blocks(message)

        self.assertEqual(self.handler._last_flush_kind, "tool_call")
        self.assertFalse(self.handler.has_streamed_answer("Need to inspect this"))

    def test_format_tool_display_read_file(self):
        """Test tool display formatting for read_file."""
        result = self.handler._format_tool_display(
            "read_file", {"file_path": "/path/to/file.py"}
        )

        self.assertEqual(result, "read_file(/path/to/file.py)")

    def test_format_tool_display_web_search(self):
        """Test tool display formatting for web_search."""
        result = self.handler._format_tool_display(
            "web_search", {"query": "python tutorial"}
        )

        self.assertEqual(result, 'web_search("python tutorial")')

    def test_format_tool_display_shell(self):
        """Test tool display formatting for shell."""
        result = self.handler._format_tool_display(
            "shell", {"command": "ls -la"}
        )

        self.assertEqual(result, 'shell("ls -la")')

    def test_deduplication_of_tool_calls(self):
        """Test that duplicate tool call IDs are not displayed twice."""
        block1 = {
            "type": "tool_call_chunk",
            "index": 0,
            "name": "read_file",
            "id": "call-dup",
            "args": {"file_path": "test.py"},
        }

        self.handler._handle_tool_call_chunk(block1)
        initial_print_count = self.console.print.call_count

        self.handler._handle_tool_call_chunk(block1)
        final_print_count = self.console.print.call_count

        self.assertEqual(initial_print_count, final_print_count)

    def test_tool_stats_tracking(self):
        """Test that tool statistics are tracked correctly."""
        message = Mock(spec=AIMessage)
        message.tool_calls = [
            {"name": "read_file", "args": {"file_path": "test.py"}, "id": "call-1"},
            {"name": "web_search", "args": {"query": "test"}, "id": "call-2"},
        ]
        messages = [message]

        self.handler._track_tool_usage(messages)
        stats = self.handler.tool_stats

        self.assertEqual(stats["tool_calls"], 2)
        self.assertIn("read_file", stats["tool_names"])
        self.assertIn("web_search", stats["tool_names"])


class TestEventHandlerIntegration(unittest.TestCase):
    """Integration tests for complete streaming flow."""

    def setUp(self):
        self.console = MagicMock()
        self.handler = DeepAgentEventHandler(
            self.console,
            file_tracker=FileOpTracker(),
            show_reasoning_steps=True,
            show_tool_calls=True,
        )

    def test_complete_streaming_flow_with_tool_call(self):
        """Test complete flow: text chunks, tool call chunks, tool result."""
        text_event1 = (
            ("agent",),
            "messages",
            (
                Mock(
                    spec=AIMessageChunk,
                    content_blocks=[{"type": "text", "text": "Let me "}],
                    chunk_position=None,
                ),
                {},
            ),
        )

        text_event2 = (
            ("agent",),
            "messages",
            (
                Mock(
                    spec=AIMessageChunk,
                    content_blocks=[{"type": "text", "text": "read that file."}],
                    chunk_position=None,
                ),
                {},
            ),
        )

        tool_chunk1 = (
            ("agent",),
            "messages",
            (
                Mock(
                    spec=AIMessageChunk,
                    content_blocks=[
                        {
                            "type": "tool_call_chunk",
                            "index": 0,
                            "name": "bash",
                            "id": "call-1",
                            "args": '{"command"',
                        }
                    ],
                    chunk_position=None,
                ),
                {},
            ),
        )

        tool_chunk2 = (
            ("agent",),
            "messages",
            (
                Mock(
                    spec=AIMessageChunk,
                    content_blocks=[
                        {
                            "type": "tool_call_chunk",
                            "index": 0,
                            "args": ': "echo hi"}',
                        }
                    ],
                    chunk_position=None,
                ),
                {},
            ),
        )

        last_chunk = (
            ("agent",),
            "messages",
            (
                Mock(
                    spec=AIMessageChunk,
                    content_blocks=[],
                    chunk_position="last",
                ),
                {},
            ),
        )

        tool_result = (
            ("agent",),
            "messages",
            (
                Mock(
                    spec=ToolMessage,
                    name="bash",
                    status="success",
                    content="done",
                    tool_call_id="call-1",
                ),
                {},
            ),
        )

        self.handler.handle_event(text_event1)
        self.handler.handle_event(text_event2)
        self.assertEqual(self.handler._pending_text, "Let me read that file.")

        self.handler.handle_event(tool_chunk1)
        self.assertEqual(len(self.handler._tool_call_buffers), 1)

        self.handler.handle_event(tool_chunk2)
        self.assertIn("call-1", self.handler._displayed_tool_ids)

        self.handler.handle_event(last_chunk)
        self.assertEqual(self.handler._pending_text, "")

        self.handler.handle_event(tool_result)
        self.assertEqual(len(self.handler._file_tracker.completed), 1)


if __name__ == "__main__":
    unittest.main()
