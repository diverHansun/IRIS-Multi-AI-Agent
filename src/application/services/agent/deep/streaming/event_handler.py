"""Streaming event processing for deep agent mode."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from src.application.cli.renderers import BaseTranscriptRenderer, DeepTranscriptRenderer

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
    step_completed: bool = False


class DeepAgentEventHandler:
    """Interpret streaming events and delegate transcript rendering."""

    def __init__(
        self,
        console_or_renderer,
        *,
        renderer: BaseTranscriptRenderer | None = None,
        file_tracker=None,
        show_reasoning_steps: bool = True,
        show_tool_calls: bool = True,
        show_tool_results: bool = True,
        show_subagent_delegations: bool = True,
        show_elapsed_time: bool = True,
    ) -> None:
        if renderer is None and isinstance(console_or_renderer, BaseTranscriptRenderer):
            renderer = console_or_renderer
        if renderer is None:
            renderer = DeepTranscriptRenderer(
                console_or_renderer,
                show_elapsed_time=show_elapsed_time,
                show_subagent_delegations=show_subagent_delegations,
            )
        self.renderer = renderer
        self.show_reasoning_steps = show_reasoning_steps
        self.show_tool_calls = show_tool_calls
        self.show_tool_results = show_tool_results
        self.show_subagent_delegations = show_subagent_delegations
        self._show_elapsed_time = show_elapsed_time

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
        self._last_flushed_text: str = ""
        self._last_flush_kind: Optional[str] = None
        self._subagent_call_index: Dict[str, int] = {}

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
            namespace_key = self._normalise_namespace(namespace)
            is_main_agent = self._is_main_namespace(namespace_key, data)

            if stream_mode == "messages":
                return self._handle_messages_stream(data, is_main_agent=is_main_agent)
            elif stream_mode == "updates":
                return self._handle_updates_stream(data, capture_state=is_main_agent)

        elif isinstance(event, dict):
            return self._handle_updates_stream(event, capture_state=True)

        return EventProcessingResult()

    def _handle_messages_stream(
        self,
        data: Any,
        *,
        is_main_agent: bool,
    ) -> EventProcessingResult:
        """Handle messages stream mode data.

        Messages stream returns (message, metadata) tuples.
        """
        if not isinstance(data, tuple) or len(data) != 2:
            return EventProcessingResult()

        message, metadata = data

        if isinstance(metadata, dict) and metadata.get("lc_source") == "summarization":
            return EventProcessingResult()

        if isinstance(message, ToolMessage):
            self._process_tool_message(message)
            return EventProcessingResult()

        if isinstance(message, (AIMessage, AIMessageChunk)):
            self._process_ai_message_content_blocks(
                message,
                capture_text=is_main_agent,
                flush_text=is_main_agent,
                render_tool_calls=is_main_agent,
            )

        return EventProcessingResult()

    def _handle_updates_stream(
        self,
        data: Dict[str, Any],
        *,
        capture_state: bool,
    ) -> EventProcessingResult:
        """Handle updates stream mode data."""
        interrupts: Tuple[Interrupt, ...] = ()
        step_completed = False

        if "__interrupt__" in data:
            value = data.get("__interrupt__", ())
            if isinstance(value, tuple):
                interrupts = value

        for node, payload in data.items():
            if node in {"__interrupt__", "__metadata__"}:
                continue
            if capture_state:
                self._render_update(node, payload)
            if self._is_tool_step_completion(payload):
                step_completed = True

        result_state = self._last_agent_state
        return EventProcessingResult(
            interrupts=interrupts,
            final_state=result_state,
            step_completed=step_completed,
        )

    def _is_tool_step_completion(self, payload: Any) -> bool:
        """Return True when an updates payload ends with a ToolMessage."""
        if not isinstance(payload, dict) or "messages" not in payload:
            return False
        messages = self._coerce_messages(payload.get("messages", []))
        return bool(messages) and isinstance(messages[-1], ToolMessage)

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

        if tool_call_id:
            self._update_subagent_call(tool_call_id, tool_status, tool_content)

        # Handle bash errors
        if tool_name == "bash" and tool_status != "success":
            self._flush_text_buffer(final=True, flush_kind="tool_call")
            if tool_content:
                self.renderer.emit_tool_error(tool_content)
            return

        # Display file operation results (only for write/edit, skip read operations)
        if record and tool_name in {"write_real_file", "edit_real_file"}:
            self._flush_text_buffer(final=True, flush_kind="tool_call")
            self.renderer.emit_file_operation(record)
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
                self._flush_text_buffer(final=True, flush_kind="tool_call")
                self.renderer.emit_tool_error(tool_content)

    def _process_ai_message_content_blocks(
        self,
        message: BaseMessage,
        *,
        capture_text: bool = True,
        flush_text: bool = True,
        render_tool_calls: bool = True,
    ) -> None:
        """Process content_blocks from AIMessage/AIMessageChunk."""
        has_content_blocks = hasattr(message, "content_blocks")
        has_tool_calls = hasattr(message, "tool_calls") and message.tool_calls
        saw_tool_block = False

        # Process content_blocks if available
        if has_content_blocks:
            for block in message.content_blocks:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")

                if block_type == "text":
                    if capture_text:
                        self._handle_text_block(block)
                elif block_type == "reasoning":
                    pass
                elif block_type == "tool_call_chunk":
                    saw_tool_block = True
                    self._handle_tool_call_chunk(
                        block,
                        render_output=render_tool_calls,
                        flush_pending=flush_text,
                    )
                elif block_type == "tool_call":
                    saw_tool_block = True
                    self._process_direct_tool_call(
                        block,
                        render_output=render_tool_calls,
                        flush_pending=flush_text,
                    )

        # Fallback for providers that expose tool calls directly on the message
        # without corresponding tool_call/tool_call_chunk content blocks.
        if has_tool_calls and not saw_tool_block:
            for tool_call in message.tool_calls:
                self._process_direct_tool_call(
                    tool_call,
                    render_output=render_tool_calls,
                    flush_pending=flush_text,
                )

        if flush_text and getattr(message, "chunk_position", None) == "last":
            self._flush_text_buffer(final=True, flush_kind="message_end")

    def _process_direct_tool_call(
        self,
        tool_call: Dict[str, Any],
        *,
        render_output: bool = True,
        flush_pending: bool = True,
    ) -> None:
        """Process a complete tool call from AIMessage.tool_calls."""
        tool_id = tool_call.get("id")
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})

        if not tool_name:
            return

        # Skip if already displayed
        if tool_id and tool_id in self._displayed_tool_ids:
            return

        if flush_pending:
            self._flush_text_buffer(final=True, flush_kind="tool_call")

        if not isinstance(tool_args, dict):
            tool_args = {"value": tool_args}

        # Register with file tracker
        if tool_id:
            self._displayed_tool_ids.add(tool_id)
            if self._file_tracker:
                self._file_tracker.start_operation(tool_name, tool_args, tool_id)

        # Display the tool call
        if render_output and self.show_tool_calls:
            self._render_tool_call(tool_name, tool_args)

    def _handle_text_block(self, block: Dict[str, Any]) -> None:
        """Accumulate text blocks for buffered rendering."""
        text = block.get("text", "")
        if text:
            self._pending_text += text

    def _handle_tool_call_chunk(
        self,
        block: Dict[str, Any],
        *,
        render_output: bool = True,
        flush_pending: bool = True,
    ) -> None:
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
            {
                "name": None,
                "id": None,
                "args": None,
                "args_parts": [],
                "render_output": render_output,
                "flush_pending": flush_pending,
            },
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

        if buffer.get("flush_pending", True):
            self._flush_text_buffer(final=True, flush_kind="tool_call")

        if buffer_id is not None:
            self._displayed_tool_ids.add(buffer_id)
            if self._file_tracker:
                self._file_tracker.start_operation(buffer_name, parsed_args, buffer_id)

        self._tool_call_buffers.pop(buffer_key, None)

        if buffer.get("render_output", True) and self.show_tool_calls:
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

        display_str = self._format_tool_display(tool_name, tool_args)
        self.renderer.emit_tool_call(display_str)

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

    def _flush_text_buffer(
        self, *, final: bool = False, flush_kind: str = "message_end"
    ) -> None:
        """Flush accumulated assistant text when appropriate."""
        if not final or not self._pending_text.strip():
            return

        text = self._pending_text.rstrip()
        self._last_flushed_text = text
        self._last_flush_kind = flush_kind

        self.renderer.emit_assistant_text(
            text,
            intermediate=(flush_kind == "tool_call"),
        )
        self._pending_text = ""

    def _start_spinner(self) -> None:
        """Start spinner if not already active."""
        self.renderer.start_spinner()

    def _stop_spinner(self) -> None:
        """Stop spinner if active."""
        self.renderer.stop_spinner()

    def start_spinner(self) -> None:
        """Public wrapper used by the conversation driver."""
        self._start_spinner()

    def stop_spinner(self) -> None:
        """Public wrapper used by the conversation driver."""
        self._stop_spinner()

    def _build_spinner_status_text(self) -> str:
        """Build spinner label with optional elapsed runtime."""
        base = "Deep agent reasoning..."
        if not self.show_elapsed_time:
            return f"[dim]{base}[/]"
        return f"[dim]{base} ({self._format_runtime_duration(self.elapsed_time)})[/]"

    @staticmethod
    def _format_runtime_duration(elapsed_seconds: float) -> str:
        """Format elapsed seconds as '<m> min <ss>s'."""
        total_seconds = max(0, int(elapsed_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes} min {seconds:02d}s"

    def _render_update(self, node: str, payload: Any) -> None:
        """Consume node update events without rendering them to the transcript."""
        self._capture_state(node, payload)

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

    def _describe_messages(
        self, node: str, messages: Sequence[BaseMessage]
    ) -> Optional[str]:
        """Generate description for messages."""
        if not messages:
            return f"{node}: (no messages)"

        last_message = messages[-1]

        if isinstance(last_message, ToolMessage):
            tool_name = getattr(last_message, "name", "unknown") or "unknown"
            tool_status = str(getattr(last_message, "status", "success") or "success").lower()

            # Never render raw tool output content in updates stream; it can be very large
            # (e.g. full file bodies from read tools) and only adds visual noise.
            if tool_status not in {"success", "ok"}:
                return f"{node}: Tool '{tool_name}' failed."
            return f"{node}: Tool '{tool_name}' completed."

        if isinstance(last_message, AIMessage):
            if last_message.tool_calls:
                if self.show_tool_calls:
                    tool_names = {
                        call.get("name", "unknown") for call in last_message.tool_calls
                    }
                    tools = ", ".join(sorted(tool_names))
                    return f"{node}: Calling tools [{tools}]"
                return f"{node}: Thinking"

            content = self._visible_text_content(last_message.content).strip()
            if not content:
                return None
            return f"{node}: Thinking"

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
        call_id = str(call.get("id", "") or "")
        subagent_type = args.get("subagent_type", "unknown")
        description = args.get("description", "")

        if call_id and call_id in self._subagent_call_index:
            index = self._subagent_call_index[call_id]
            self._subagent_calls[index]["description"] = self._truncate(
                description,
                limit=120,
            )
            return

        self._subagent_calls.append(
            {
                "subagent_type": subagent_type,
                "description": self._truncate(description, limit=120),
                "call_id": call_id or None,
                "status": "delegated",
                "result": "",
            }
        )
        if call_id:
            self._subagent_call_index[call_id] = len(self._subagent_calls) - 1

    def _update_subagent_call(
        self,
        tool_call_id: str,
        tool_status: Any,
        tool_content: str,
    ) -> None:
        """Update tracked subagent status/result from a matching tool message."""
        index = self._subagent_call_index.get(str(tool_call_id))
        if index is None:
            return

        record = self._subagent_calls[index]
        record["status"] = self._normalise_subagent_status(tool_status, tool_content)
        record["result"] = self._truncate(tool_content.strip(), limit=150) if tool_content.strip() else ""

    @staticmethod
    def _normalise_subagent_status(tool_status: Any, tool_content: str) -> str:
        """Map tool message status/content to a stable user-facing subagent status."""
        status = str(tool_status or "").strip().lower()
        content = tool_content.strip().lower()

        if status in {"error", "failed", "failure"}:
            return "failed"
        if content.startswith("[timeout]") or "timed out" in content:
            return "timeout"
        if content.startswith("subagent execution failed") or content.startswith("error:"):
            return "failed"
        if status in {"success", "ok", "completed"} or not status:
            return "completed"
        return status

    def render_summary(self) -> None:
        """Display an execution summary after streaming completes."""
        self.renderer.emit_summary(self.tool_stats)

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

    def has_streamed_answer(self, answer: str) -> bool:
        """Return whether the final answer has already been streamed."""
        return (
            self._last_flush_kind == "message_end"
            and self._last_flushed_text.strip() == answer.strip()
        )

    @staticmethod
    def _normalise_namespace(namespace: Any) -> Tuple[Any, ...]:
        """Convert stream namespace into a stable tuple."""
        if namespace in (None, (), []):
            return ()
        if isinstance(namespace, tuple):
            return namespace
        if isinstance(namespace, list):
            return tuple(namespace)
        return (namespace,)

    @staticmethod
    def _is_main_namespace(namespace: Tuple[Any, ...], data: Any) -> bool:
        """Return whether a namespace belongs to the main agent graph.

        LangGraph emits an empty namespace for the main graph. Our current
        compatibility tests still use single-item namespaces such as
        ``("agent",)`` and ``("tools",)`` for top-level events, so keep
        those visible as well and treat everything else as subgraph output.
        """
        if not namespace:
            return True
        if len(namespace) == 1 and str(namespace[0]) in {"agent", "tools"}:
            return True
        if isinstance(data, dict) and len(namespace) == 1 and namespace[0] in data:
            return True
        return False

    @property
    def elapsed_time(self) -> float:
        """Return the total elapsed wall-clock time since handler creation."""
        return time.perf_counter() - self._start_time

    @property
    def show_elapsed_time(self) -> bool:
        """Expose elapsed footer preference."""
        return self._show_elapsed_time

    @show_elapsed_time.setter
    def show_elapsed_time(self, value: bool) -> None:
        self._show_elapsed_time = bool(value)
        if hasattr(self.renderer, "show_elapsed_time"):
            self.renderer.show_elapsed_time = self._show_elapsed_time

    @staticmethod
    def _truncate(text: str, limit: int = 160) -> str:
        """Truncate text to specified limit."""
        return text if len(text) <= limit else text[: limit - 3] + "..."

    @staticmethod
    def _visible_text_content(content: Any) -> str:
        """Extract visible text content from message payloads."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            return "".join(parts)
        return str(content) if content is not None else ""
