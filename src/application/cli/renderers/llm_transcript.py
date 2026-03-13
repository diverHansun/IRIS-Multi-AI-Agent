"""Terminal renderer for LLM conversations."""

from __future__ import annotations

from typing import Any

from rich.text import Text

from src.application.cli.theme import COLORS

from .base import BaseTranscriptRenderer
from .events import TranscriptEvent


class LLMTranscriptRenderer(BaseTranscriptRenderer):
    """Render LLM transcript events, including token streaming."""

    def __init__(self, console: Any) -> None:
        self.console = console
        self._status: Any = None
        self._stream_open = False

    def emit(self, event: TranscriptEvent) -> None:
        if event.kind == "assistant_text":
            self.stop_spinner()
            if self._stream_open:
                self._close_stream_line()
            self.console.print(
                Text.assemble(
                    ("LLM >", f"bold {COLORS['info']}"),
                    (" ", ""),
                    (event.text or "", COLORS["text_primary"]),
                )
            )
            return
        if event.kind == "assistant_chunk":
            self._render_chunk(event.text or "")
            return
        if event.kind == "stream_complete":
            self._finish_stream()
            return
        if event.kind == "warning":
            self.stop_spinner()
            if self._stream_open:
                self._close_stream_line()
            self.console.print(event.text or "", style=COLORS["warning"])
            return
        if event.kind == "error":
            self.stop_spinner()
            if self._stream_open:
                self._close_stream_line()
            self.console.print(event.text or "", style=COLORS["error"])
            return
        if event.kind == "info":
            self.console.print(event.text or "", style=COLORS["text_dim"])
            return

    def start_spinner(self) -> None:
        if self._status is not None:
            return
        status_factory = getattr(self.console, "status", None)
        if not callable(status_factory):
            return
        status = status_factory("[dim]LLM thinking...[/]")
        enter = getattr(status, "__enter__", None)
        if callable(enter):
            enter()
            self._status = status

    def stop_spinner(self) -> None:
        status = self._status
        self._status = None
        if status is None:
            return
        exit_fn = getattr(status, "__exit__", None)
        if callable(exit_fn):
            exit_fn(None, None, None)

    def stream_chunk(self, chunk: str) -> None:
        self.emit(TranscriptEvent(kind="assistant_chunk", text=chunk))

    def finish_stream(self) -> None:
        self.emit(TranscriptEvent(kind="stream_complete"))

    def _render_chunk(self, chunk: str) -> None:
        if not chunk:
            return
        self.stop_spinner()
        if not self._stream_open:
            self.console.print(
                Text.assemble(
                    ("LLM >", f"bold {COLORS['info']}"),
                    (" ", ""),
                    (chunk, COLORS["text_primary"]),
                ),
                end="",
            )
            self._stream_open = True
            return
        self.console.print(chunk, end="", style=COLORS["text_primary"])

    def _finish_stream(self) -> None:
        self.stop_spinner()
        if self._stream_open:
            self.console.print()
            self._stream_open = False

    def _close_stream_line(self) -> None:
        self.console.print()
        self._stream_open = False

