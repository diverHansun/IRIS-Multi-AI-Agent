"""Streaming event processing for deep agent mode."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from rich.markup import escape

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

try:
    from langchain_core.messages import AIMessageChunk
except ImportError:
    AIMessageChunk = AIMessage

from langgraph.types import Interrupt


@dataclass
class EventProcessingResult:
    """Represents the outcome of processing a single streaming event."""

    interrupts: Tuple[Interrupt, ...] = ()
    final_state: Optional[Dict[str, Any]] = None


class DeepAgentEventHandler:
    """Render streaming updates and collect execution statistics."""

    def __init__(
        self,
        console,
        *,
        file_tracker=None,
        show_reasoning_steps: bool = True,
        show_tool_calls: bool = True,
        show_tool_results: bool = True,
        show_subagent_delegations: bool = True,
        show_elapsed_time: bool = True,
    ) -> None:
        self.console = console
        self.show_reasoning_steps = show_reasoning_steps
        self.show_tool_calls = show_tool_calls
        self.show_tool_results = show_tool_results
        self.show_subagent_delegations = show_subagent_delegations
        self.show_elapsed_time = show_elapsed_time

        self._start_time = time.perf_counter()
        self._step = 0
        self._tool_call_count = 0
        self._tool_names: set[str] = set()
        self._subagent_calls: List[Dict[str, Any]] = []
        self._last_agent_state: Optional[Dict[str, Any]] = None

        self._tool_call_buffers: Dict[Union[str, int], Dict[str, Any]] = {}
        self._displayed_tool_ids: set[str] = set()
        self._pending_text: str = ""
        self._file_tracker = file_tracker

        self._spinner_active: bool = False
        self._has_responded: bool = False

    def handle_event(
        self, event: Union[Dict[str, Any], Tuple[Any, str, Any]]
    ) -> EventProcessingResult:
        """Process a streaming event and return interrupt/final state information.

        Supports both:
        - Tuple format: (namespace, stream_mode, data) for dual-mode streaming
        - Dict format: event dict for backwards compatibility with single-mode
        """
        interrupts: Tuple[Interrupt, ...] = ()

        if isinstance(event, tuple) and len(event) == 3:
            namespace, stream_mode, data = event

            if stream_mode == "messages":
                return self._handle_messages_stream(data)
            elif stream_mode == "updates":
                return self._handle_updates_stream(data)

        elif isinstance(event, dict):
            return self._handle_updates_stream(event)

        return EventProcessingResult()

    def _handle_messages_stream(self, data: Any) -> EventProcessingResult:
        """Handle messages stream mode data.

        Messages stream returns (message, metadata) tuples.
        """
        if not isinstance(data, tuple) or len(data) != 2:
            return EventProcessingResult()

        message, metadata = data

        if isinstance(message, ToolMessage):
            self._process_tool_message(message)
            return EventProcessingResult()

        if isinstance(message, (AIMessage, AIMessageChunk)):
            self._process_ai_message_content_blocks(message)

        return EventProcessingResult()

    def _handle_updates_stream(self, data: Dict[str, Any]) -> EventProcessingResult:
        """Handle updates stream mode data."""
        interrupts: Tuple[Interrupt, ...] = ()

        if "__interrupt__" in data:
            value = data.get("__interrupt__", ())
            if isinstance(value, tuple):
                interrupts = value

        for node, payload in data.items():
            if node in {"__interrupt__", "__metadata__"}:
                continue
            self._render_update(node, payload)

        result_state = self._last_agent_state
        return EventProcessingResult(interrupts=interrupts, final_state=result_state)

    def _process_tool_message(self, message: ToolMessage) -> None:
        """Process tool completion messages and handle errors."""
        tool_name = getattr(message, "name", "")
        tool_status = getattr(message, "status", "success")
        tool_call_id = getattr(message, "tool_call_id", None)
        content = message.content

        if isinstance(content, list):
            content_parts = []
            for item in content:
                if isinstance(item, str):
                    content_parts.append(item)
                else:
                    content_parts.append(str(item))
            tool_content = "\n".join(content_parts)
        else:
            tool_content = str(content) if content is not None else ""

        # Track file operations if tracker is available
        record = None
        if self._file_tracker:
            record = self._file_tracker.complete_with_message(message)

        # Handle bash errors
        if tool_name == "bash" and tool_status != "success":
            self._flush_text_buffer(final=True)
            if tool_content:
                self._stop_spinner()
                self.console.print()
                self.console.print(tool_content, style="red", markup=False)
                self.console.print()
            return

        # Display file operation results (only for write/edit, skip read operations)
        if record and tool_name in {"write_real_file", "edit_real_file"}:
            from ..hitl.file_ops import render_file_operation
            self._flush_text_buffer(final=True)
            self._stop_spinner()
            render_file_operation(record, self.console)
            return

        # Skip read operation results - they are internal and don't need to be shown
        # Real filesystem: read, list, glob, grep
        # Virtual filesystem: read, list
        if tool_name in (
            "read_real_file",
            "read_virtual_file",
            "list_real_files",
            "list_virtual_files",
            "write_virtual_file",
            "edit_virtual_file",
            "glob_real_files",
            "grep_real_files",
        ):
            return

        # Handle generic tool errors
        if tool_content and isinstance(tool_content, str):
            stripped = tool_content.lstrip()
            if stripped.lower().startswith("error"):
                self._flush_text_buffer(final=True)
                self._stop_spinner()
                self.console.print()
                self.console.print(tool_content, style="red", markup=False)
                self.console.print()

    def _process_ai_message_content_blocks(self, message: BaseMessage) -> None:
        """Process content_blocks from AIMessage/AIMessageChunk."""
        has_content_blocks = hasattr(message, "content_blocks")
        has_tool_calls = hasattr(message, "tool_calls") and message.tool_calls

        # Process content_blocks if available
        if has_content_blocks:
            for block in message.content_blocks:
                block_type = block.get("type")

                if block_type == "text":
                    self._handle_text_block(block)
                elif block_type == "reasoning":
                    pass
                elif block_type == "tool_call_chunk":
                    self._handle_tool_call_chunk(block)

            if getattr(message, "chunk_position", None) == "last":
                self._flush_text_buffer(final=True)

        # IMPORTANT: Also process tool_calls directly if present
        # This handles cases where AIMessage has tool_calls but they're not in content_blocks
        if has_tool_calls:
            for tool_call in message.tool_calls:
                self._process_direct_tool_call(tool_call)

    def _process_direct_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Process a complete tool call from AIMessage.tool_calls."""
        tool_id = tool_call.get("id")
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})

        if not tool_name:
            return

        # Skip if already displayed
        if tool_id and tool_id in self._displayed_tool_ids:
            return

        # Register with file tracker
        if tool_id:
            self._displayed_tool_ids.add(tool_id)
            if self._file_tracker:
                self._file_tracker.start_operation(tool_name, tool_args, tool_id)

        # Display the tool call
        if self.show_tool_calls:
            self._render_tool_call(tool_name, tool_args)

    def _handle_text_block(self, block: Dict[str, Any]) -> None:
        """Accumulate text blocks for buffered rendering."""
        text = block.get("text", "")
        if text:
            self._pending_text += text

    def _handle_tool_call_chunk(self, block: Dict[str, Any]) -> None:
        """Buffer and process tool call chunks."""
        chunk_index = block.get("index")
        chunk_id = block.get("id")
        chunk_name = block.get("name")
        chunk_args = block.get("args")

        if chunk_index is not None:
            buffer_key: Union[str, int] = chunk_index
        elif chunk_id is not None:
            buffer_key = chunk_id
        else:
            buffer_key = f"unknown-{len(self._tool_call_buffers)}"

        buffer = self._tool_call_buffers.setdefault(
            buffer_key,
            {"name": None, "id": None, "args": None, "args_parts": []},
        )

        if chunk_name:
            buffer["name"] = chunk_name
        if chunk_id:
            buffer["id"] = chunk_id

        if isinstance(chunk_args, dict):
            buffer["args"] = chunk_args
            buffer["args_parts"] = []
        elif isinstance(chunk_args, str) and chunk_args:
            parts: List[str] = buffer.setdefault("args_parts", [])
            if not parts or chunk_args != parts[-1]:
                parts.append(chunk_args)
            buffer["args"] = "".join(parts)
        elif chunk_args is not None:
            buffer["args"] = chunk_args

        self._try_display_tool_call(buffer_key, buffer)

    def _try_display_tool_call(
        self, buffer_key: Union[str, int], buffer: Dict[str, Any]
    ) -> None:
        """Try to display tool call if complete and valid."""
        buffer_name = buffer.get("name")
        buffer_id = buffer.get("id")

        if buffer_name is None:
            return

        if buffer_id and buffer_id in self._displayed_tool_ids:
            return

        parsed_args = buffer.get("args")
        if isinstance(parsed_args, str):
            if not parsed_args:
                return
            try:
                parsed_args = json.loads(parsed_args)
            except json.JSONDecodeError:
                return
        elif parsed_args is None:
            return

        if not isinstance(parsed_args, dict):
            parsed_args = {"value": parsed_args}

        self._flush_text_buffer(final=True)

        if buffer_id is not None:
            self._displayed_tool_ids.add(buffer_id)
            if self._file_tracker:
                self._file_tracker.start_operation(buffer_name, parsed_args, buffer_id)

        self._tool_call_buffers.pop(buffer_key, None)

        if self.show_tool_calls:
            self._render_tool_call(buffer_name, parsed_args)

    def _render_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        """Render a tool call display.

        Only renders write/edit operations. Read/grep/glob operations are hidden
        as they are internal to the agent's reasoning process.
        """
        # Skip read operations - they are internal and don't need to be shown
        # Real filesystem: read, list, glob, grep
        # Virtual filesystem: read, list
        if tool_name in (
            "read_file",
            "read_real_file",
            "read_virtual_file",
            "list_real_files",
            "list_virtual_files",
            "write_virtual_file",
            "edit_virtual_file",
            "grep_real_files",
            "glob_real_files",
        ):
            return

        self._stop_spinner()

        if not self._has_responded:
            self._has_responded = True

        display_str = self._format_tool_display(tool_name, tool_args)
        self.console.print(f"  Tool: {escape(display_str)}", style="dim cyan", markup=False)

        self._start_spinner()

    def _format_tool_display(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Format tool call for display."""
        if tool_name in ("read_file", "write_file", "edit_file"):
            path_value = tool_args.get("file_path") or tool_args.get("path")
            if path_value is not None:
                return f"{tool_name}({path_value})"

        elif tool_name == "web_search":
            if "query" in tool_args:
                query = str(tool_args["query"])
                query = query[:100] if len(query) > 100 else query
                return f'{tool_name}("{query}")'

        elif tool_name == "grep":
            if "pattern" in tool_args:
                pattern = str(tool_args["pattern"])
                pattern = pattern[:70] if len(pattern) > 70 else pattern
                return f'{tool_name}("{pattern}")'

        elif tool_name == "shell":
            if "command" in tool_args:
                command = str(tool_args["command"])
                command = command[:120] if len(command) > 120 else command
                return f'{tool_name}("{command}")'

        args_str = ", ".join(f"{k}={v!r}" for k, v in tool_args.items())
        args_str = args_str[:160] if len(args_str) > 160 else args_str
        return f"{tool_name}({args_str})"

    def _flush_text_buffer(self, *, final: bool = False) -> None:
        """Flush accumulated assistant text when appropriate."""
        if not final or not self._pending_text.strip():
            return

        self._stop_spinner()

        if not self._has_responded:
            self.console.print("Agent:", style="bold blue", markup=False)
            self._has_responded = True

        self.console.print(escape(self._pending_text.rstrip()), style="white")
        self._pending_text = ""

    def _start_spinner(self) -> None:
        """Start spinner if not already active."""
        if not self._spinner_active and self.show_reasoning_steps:
            self._spinner_active = True

    def _stop_spinner(self) -> None:
        """Stop spinner if active."""
        if self._spinner_active:
            self._spinner_active = False

    def _render_update(self, node: str, payload: Any) -> None:
        """Render node update event (for updates stream mode)."""
        if not self.show_reasoning_steps:
            self._capture_state(node, payload)
            return

        description = self._describe_update(node, payload)
        if description is None:
            return

        self._step += 1
        if self.show_elapsed_time:
            elapsed = time.perf_counter() - self._start_time
            prefix = f"  Step {self._step} | {elapsed:0.1f}s | "
        else:
            prefix = f"  Step {self._step} | "

        self.console.print(prefix + escape(description))

    def _describe_update(self, node: str, payload: Any) -> Optional[str]:
        """Generate description for a node update."""
        messages = self._capture_state(node, payload)
        if messages:
            return self._describe_messages(node, messages)

        if isinstance(payload, dict):
            rendered = ", ".join(f"{key}={value!r}" for key, value in payload.items())
            return f"{node}: {rendered}" if rendered else f"{node}: (no changes)"

        return f"{node}: {payload!r}"

    def _capture_state(
        self, node: str, payload: Any
    ) -> Optional[Sequence[BaseMessage]]:
        """Capture agent state from payload."""
        if isinstance(payload, dict) and "messages" in payload:
            messages_raw = payload.get("messages", [])
            messages = self._coerce_messages(messages_raw)
            self._last_agent_state = payload
            if messages:
                self._track_tool_usage(messages)
                return messages
        return None

    def _coerce_messages(self, raw: Iterable[Any]) -> List[BaseMessage]:
        """Convert raw message data to BaseMessage list."""
        messages: List[BaseMessage] = []
        for item in raw:
            if isinstance(item, BaseMessage):
                messages.append(item)
            else:
                try:
                    content = item.get("content", repr(item))
                except AttributeError:
                    content = repr(item)
                messages.append(AIMessage(content=content))
        return messages

    def _describe_messages(self, node: str, messages: Sequence[BaseMessage]) -> str:
        """Generate description for messages."""
        if not messages:
            return f"{node}: (no messages)"

        last_message = messages[-1]

        if isinstance(last_message, ToolMessage):
            if not self.show_tool_results:
                return f"{node}: Tool '{last_message.name}' completed."
            return f"{node}: Tool '{last_message.name}' -> {last_message.content}"

        if isinstance(last_message, AIMessage):
            content_snippet = self._truncate(str(last_message.content))
            if last_message.tool_calls and self.show_tool_calls:
                tool_names = {
                    call.get("name", "unknown") for call in last_message.tool_calls
                }
                tools = ", ".join(sorted(tool_names))
                return f"{node}: Calling tools [{tools}]"
            return f"{node}: {content_snippet}"

        return f"{node}: {self._truncate(str(last_message.content))}"

    def _track_tool_usage(self, messages: Sequence[BaseMessage]) -> None:
        """Track tool usage statistics."""
        for message in messages:
            if isinstance(message, AIMessage) and message.tool_calls:
                self._tool_call_count += len(message.tool_calls)
                for call in message.tool_calls:
                    name = call.get("name")
                    if name:
                        self._tool_names.add(name)
                    if self.show_subagent_delegations and name == "task":
                        args = call.get("args", {}) if isinstance(call, dict) else {}
                        self._record_subagent_call(call, args)

    def _record_subagent_call(
        self, call: Dict[str, Any], args: Dict[str, Any]
    ) -> None:
        """Record subagent delegation."""
        subagent_type = args.get("subagent_type", "unknown")
        description = args.get("description", "")
        self._subagent_calls.append(
            {
                "subagent_type": subagent_type,
                "description": self._truncate(description, limit=120),
                "call_id": call.get("id"),
            }
        )

    def render_summary(self) -> None:
        """Display an execution summary after streaming completes."""
        if not self.show_reasoning_steps or self._step == 0:
            return

        lines = [
            "",
            "Summary:",
            f"  - Reasoning steps: {self._step}",
        ]
        if self._tool_call_count:
            names = escape(", ".join(sorted(self._tool_names)))
            lines.append(f"  - Tool calls: {self._tool_call_count} ({names})")
        if self._subagent_calls:
            lines.append(f"  - Subagent delegations: {len(self._subagent_calls)}")
        total_time = time.perf_counter() - self._start_time
        lines.append(f"  - Total time: {total_time:0.1f}s")
        self.console.print("\n".join(lines))

    @property
    def last_agent_state(self) -> Optional[Dict[str, Any]]:
        """Return the last captured agent state."""
        return self._last_agent_state

    @property
    def tool_stats(self) -> Dict[str, Any]:
        """Expose tracked tool statistics."""
        return {
            "tool_calls": self._tool_call_count,
            "tool_names": sorted(self._tool_names),
            "subagent_calls": list(self._subagent_calls),
        }

    @staticmethod
    def _truncate(text: str, limit: int = 160) -> str:
        """Truncate text to specified limit."""
        return text if len(text) <= limit else text[: limit - 3] + "..."
