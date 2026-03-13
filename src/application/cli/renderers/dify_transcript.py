"""Terminal renderer for Dify conversations."""

from __future__ import annotations

from typing import Any, Mapping

from src.application.cli.theme import COLORS

from .base import BaseTranscriptRenderer
from .events import TranscriptEvent


class DifyTranscriptRenderer(BaseTranscriptRenderer):
    """Render Dify streaming transcript events."""

    def __init__(self, console: Any) -> None:
        self.console = console
        self._status: Any = None
        self._stream_open = False

    def emit(self, event: TranscriptEvent) -> None:
        if event.kind == "assistant_chunk":
            self._render_chunk(event.text or "")
            return
        if event.kind == "assistant_text":
            self.stop_spinner()
            if self._stream_open:
                self.console.print()
                self._stream_open = False
            self.console.print(event.text or "", style=COLORS["text_primary"])
            return
        if event.kind == "stream_complete":
            self._finish_stream(event.payload)
            return
        if event.kind == "agent_thought":
            self.stop_spinner()
            if self._stream_open:
                self.console.print()
                self._stream_open = False
            position = event.payload.get("position", 0)
            tool = event.payload.get("tool", "")
            if tool:
                self.console.print(
                    f"[Agent Step {position}] {tool} ✓",
                    style=COLORS["info"],
                )
            return
        if event.kind == "file":
            self.stop_spinner()
            if self._stream_open:
                self.console.print()
                self._stream_open = False
            self.console.print(f"File: {event.text or 'Unknown file'}", style=COLORS["info"])
            return
        if event.kind == "metadata":
            self._render_metadata(event.payload)
            return
        if event.kind == "warning":
            self.stop_spinner()
            if self._stream_open:
                self.console.print()
                self._stream_open = False
            self.console.print(event.text or "", style=COLORS["warning"])
            return
        if event.kind == "error":
            self.stop_spinner()
            if self._stream_open:
                self.console.print()
                self._stream_open = False
            self.console.print(event.text or "", style=COLORS["error"])
            return
        if event.kind == "info":
            if self._stream_open:
                self.console.print()
                self._stream_open = False
            self.console.print(event.text or "", style=COLORS["text_dim"])
            return

    def start_spinner(self) -> None:
        if self._status is not None:
            return
        status_factory = getattr(self.console, "status", None)
        if not callable(status_factory):
            return
        status = status_factory("Thinking...", spinner="dots")
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

    def finish_stream(self, stats: Mapping[str, Any] | None = None) -> None:
        self.emit(TranscriptEvent(kind="stream_complete", payload=stats or {}))

    def _render_chunk(self, chunk: str) -> None:
        if not chunk:
            return
        self.stop_spinner()
        self.console.print(chunk, end="", style=COLORS["text_primary"])
        self._stream_open = True

    def _finish_stream(self, payload: Mapping[str, Any]) -> None:
        self.stop_spinner()
        if self._stream_open:
            self.console.print()
            self._stream_open = False
        if not payload:
            return
        elapsed = payload.get("elapsed_time")
        total_chars = payload.get("total_chars")
        chars_per_second = payload.get("chars_per_second")
        total_chunks = payload.get("total_chunks")
        if elapsed is not None and total_chars is not None and chars_per_second is not None and total_chunks is not None:
            self.console.print(
                f"Response complete | {elapsed:.2f}s | {total_chars} chars | "
                f"{chars_per_second:.1f} chars/s | {total_chunks} chunks",
                style=COLORS["text_dim"],
            )
        elif total_chunks is not None:
            self.console.print(
                f"Response complete ({total_chunks} fragments)",
                style=COLORS["text_dim"],
            )

    def _render_metadata(self, payload: Mapping[str, Any]) -> None:
        usage = payload.get("usage")
        if usage is not None:
            self.console.print(f"\nToken usage: {usage}", style=COLORS["text_dim"])
        resources = payload.get("retriever_resources")
        if resources:
            self.console.print(
                f"\nReferenced resources: {len(resources)} items",
                style=COLORS["text_dim"],
            )
