"""Streaming event processing for deep agent mode."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from rich.markup import escape

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
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

    def handle_event(self, event: Dict[str, Any]) -> EventProcessingResult:
        """Process a streaming event and return interrupt/final state information."""
        interrupts: Tuple[Interrupt, ...] = ()

        if "__interrupt__" in event:
            value = event.get("__interrupt__", ())
            if isinstance(value, tuple):
                interrupts = value

        for node, payload in event.items():
            if node in {"__interrupt__", "__metadata__"}:
                continue
            self._render_update(node, payload)

        result_state = self._last_agent_state
        return EventProcessingResult(interrupts=interrupts, final_state=result_state)

    def _render_update(self, node: str, payload: Any) -> None:
        if not self.show_reasoning_steps:
            # Still update state even if we skip rendering.
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
        messages = self._capture_state(node, payload)
        if messages:
            return self._describe_messages(node, messages)

        if isinstance(payload, dict):
            rendered = ", ".join(f"{key}={value!r}" for key, value in payload.items())
            return f"{node}: {rendered}" if rendered else f"{node}: (no changes)"

        return f"{node}: {payload!r}"

    def _capture_state(self, node: str, payload: Any) -> Optional[Sequence[BaseMessage]]:
        if isinstance(payload, dict) and "messages" in payload:
            messages_raw = payload.get("messages", [])
            messages = self._coerce_messages(messages_raw)
            self._last_agent_state = payload
            if messages:
                self._track_tool_usage(messages)
                return messages
        return None

    def _coerce_messages(self, raw: Iterable[Any]) -> List[BaseMessage]:
        messages: List[BaseMessage] = []
        for item in raw:
            if isinstance(item, BaseMessage):
                messages.append(item)
            else:
                # Fallback: convert dict-like structures into string messages.
                try:
                    content = item.get("content", repr(item))  # type: ignore[attr-defined]
                except AttributeError:
                    content = repr(item)
                messages.append(AIMessage(content=content))
        return messages

    def _describe_messages(self, node: str, messages: Sequence[BaseMessage]) -> str:
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
                tool_names = {call.get("name", "unknown") for call in last_message.tool_calls}
                tools = ", ".join(sorted(tool_names))
                return f"{node}: Calling tools [{tools}]"
            return f"{node}: {content_snippet}"

        return f"{node}: {self._truncate(str(last_message.content))}"

    def _track_tool_usage(self, messages: Sequence[BaseMessage]) -> None:
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

    def _record_subagent_call(self, call: Dict[str, Any], args: Dict[str, Any]) -> None:
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
            lines.append(
                f"  - Subagent delegations: {len(self._subagent_calls)}"
            )
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
        return text if len(text) <= limit else text[: limit - 3] + "..."
