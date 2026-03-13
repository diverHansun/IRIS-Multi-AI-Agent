"""Terminal renderer for Basic agent conversations."""

from __future__ import annotations

from typing import Any, Mapping

from rich.text import Text

from src.application.cli.theme import COLORS

from .base import BaseTranscriptRenderer
from .events import TranscriptEvent


class BasicTranscriptRenderer(BaseTranscriptRenderer):
    """Render basic agent transcript events."""

    def __init__(self, console: Any) -> None:
        self.console = console
        self._status: Any = None

    def emit(self, event: TranscriptEvent) -> None:
        if event.kind == "assistant_text":
            self.stop_spinner()
            self.console.print(
                Text.assemble(
                    ("BasicAgent >", f"bold {COLORS['agent']}"),
                    (" ", ""),
                    (event.text or "", COLORS["text_primary"]),
                )
            )
            return
        if event.kind == "summary":
            self._render_summary(event.payload)
            return
        if event.kind == "warning":
            self.stop_spinner()
            self.console.print(event.text or "", style=COLORS["warning"])
            return
        if event.kind == "error":
            self.stop_spinner()
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
        status = status_factory("[dim]Agent reasoning...[/]")
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

    def _render_summary(self, payload: Mapping[str, Any]) -> None:
        tool_calls = int(payload.get("tool_calls", 0) or 0)
        if not tool_calls:
            return
        tool_names = list(payload.get("tool_names", []) or [])
        if tool_names:
            self.console.print(
                f"Used {len(tool_names)} tools ({tool_calls} calls): {', '.join(tool_names)}",
                style=COLORS["text_dim"],
            )
        else:
            self.console.print(f"Used {tool_calls} tool calls", style=COLORS["text_dim"])

