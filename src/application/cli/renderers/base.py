"""Base interfaces for terminal transcript renderers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .events import TranscriptEvent
from .spinner import SpinnerState


class BaseTranscriptRenderer(ABC):
    """Render structured transcript events to a target surface."""

    @abstractmethod
    def emit(self, event: TranscriptEvent) -> None:
        """Render a single transcript event."""

    def start_spinner(self) -> None:
        """Start any waiting indicator."""

    def stop_spinner(self) -> None:
        """Stop any waiting indicator."""

    def update_spinner_state(self, state: SpinnerState) -> None:
        """Update the semantic waiting state for the active transcript."""
        if state.visible:
            self.start_spinner()
            return
        self.stop_spinner()

    def emit_assistant_text(self, text: str, *, intermediate: bool = False) -> None:
        self.emit(
            TranscriptEvent(
                kind="assistant_text",
                text=text,
                payload={"intermediate": intermediate},
            )
        )

    def emit_tool_call(self, display_text: str) -> None:
        self.emit(TranscriptEvent(kind="tool_call", text=display_text))

    def emit_tool_error(self, text: str) -> None:
        self.emit(TranscriptEvent(kind="tool_error", text=text))

    def emit_file_operation(self, record: Any) -> None:
        self.emit(TranscriptEvent(kind="file_operation", payload={"record": record}))

    def emit_elapsed(self, elapsed_time: float) -> None:
        self.emit(TranscriptEvent(kind="elapsed", payload={"elapsed_time": elapsed_time}))

    def emit_summary(self, tool_stats: dict[str, Any]) -> None:
        self.emit(TranscriptEvent(kind="summary", payload=tool_stats))

    def emit_info(self, text: str) -> None:
        self.emit(TranscriptEvent(kind="info", text=text))

    def emit_warning(self, text: str) -> None:
        self.emit(TranscriptEvent(kind="warning", text=text))

    def emit_error(self, text: str) -> None:
        self.emit(TranscriptEvent(kind="error", text=text))
