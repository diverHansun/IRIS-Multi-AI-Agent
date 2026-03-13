"""Terminal transcript renderer for Deep agent mode."""

from __future__ import annotations

import threading
import time
from typing import Any, Mapping

from rich.markup import escape
from rich.text import Text

from src.application.cli.theme import COLORS
from .base import BaseTranscriptRenderer
from .events import TranscriptEvent
from .spinner import SpinnerState


class DeepTranscriptRenderer(BaseTranscriptRenderer):
    """Render compact Deep agent transcript events to a Rich console."""

    def __init__(
        self,
        console: Any,
        *,
        show_elapsed_time: bool = True,
        show_subagent_delegations: bool = True,
    ) -> None:
        self.console = console
        self.show_elapsed_time = show_elapsed_time
        self.show_subagent_delegations = show_subagent_delegations

        self._start_time = time.perf_counter()
        self._spinner_active = False
        self._spinner_status: Any = None
        self._spinner_update_thread: threading.Thread | None = None
        self._spinner_stop_event = threading.Event()
        self._has_responded = False
        self._spinner_state = SpinnerState.idle()

    def emit(self, event: TranscriptEvent) -> None:
        kind = event.kind
        if kind == "assistant_text":
            self._render_assistant_text(
                event.text or "",
                intermediate=bool(event.payload.get("intermediate", False)),
            )
            return
        if kind == "tool_call":
            self._render_tool_call(event.text or "")
            return
        if kind == "tool_error":
            self._render_tool_error(event.text or "")
            return
        if kind == "file_operation":
            record = event.payload.get("record")
            if record is not None:
                self._render_file_operation(record)
            return
        if kind == "elapsed":
            self._render_elapsed(float(event.payload.get("elapsed_time", 0.0)))
            return
        if kind == "summary":
            self._render_summary(event.payload)
            return
        if kind == "info":
            self._render_plain(event.text or "", COLORS["text_dim"])
            return
        if kind == "warning":
            self._render_plain(event.text or "", COLORS["warning"])
            return
        if kind == "error":
            self._render_plain(event.text or "", COLORS["error"])
            return
        if kind == "spinner_start":
            self.start_spinner()
            return
        if kind == "spinner_stop":
            self.stop_spinner()
            return

    def start_spinner(self) -> None:
        self.update_spinner_state(SpinnerState.thinking())

    def stop_spinner(self) -> None:
        self.update_spinner_state(SpinnerState.idle())

    def update_spinner_state(self, state: SpinnerState) -> None:
        self._spinner_state = state
        if not state.visible:
            self._deactivate_spinner()
            return
        if not self._spinner_active:
            self._activate_spinner()
            return
        self._refresh_spinner_text()

    def build_spinner_status_text(self) -> str:
        """Return the current spinner status label."""
        return self._build_spinner_status_text()

    def _activate_spinner(self) -> None:
        if self._spinner_active:
            return
        self._spinner_active = True
        self._spinner_stop_event.clear()
        status_factory = getattr(self.console, "status", None)
        if not callable(status_factory):
            return

        try:
            spinner_status = status_factory(
                self._build_spinner_status_text(),
                spinner="dots",
            )
            enter = getattr(spinner_status, "__enter__", None)
            if callable(enter):
                enter()
                self._spinner_status = spinner_status
                update = getattr(spinner_status, "update", None)
                if callable(update):
                    self._spinner_update_thread = threading.Thread(
                        target=self._run_spinner_updater,
                        name="deep-agent-spinner",
                        daemon=True,
                    )
                    self._spinner_update_thread.start()
        except Exception:
            self._spinner_status = None

    def _deactivate_spinner(self) -> None:
        if not self._spinner_active:
            return

        self._spinner_active = False
        self._spinner_stop_event.set()
        spinner_status = self._spinner_status
        self._spinner_status = None
        spinner_thread = self._spinner_update_thread
        self._spinner_update_thread = None
        if spinner_thread and spinner_thread.is_alive():
            spinner_thread.join(timeout=0.2)
        if spinner_status is None:
            return

        exit_fn = getattr(spinner_status, "__exit__", None)
        if callable(exit_fn):
            try:
                exit_fn(None, None, None)
            except Exception:
                pass

    @property
    def has_responded(self) -> bool:
        return self._has_responded

    @property
    def elapsed_time(self) -> float:
        return time.perf_counter() - self._start_time

    def _run_spinner_updater(self) -> None:
        last_second = -1
        while not self._spinner_stop_event.wait(0.2):
            elapsed_seconds = int(self.elapsed_time)
            if elapsed_seconds == last_second:
                continue
            last_second = elapsed_seconds
            spinner_status = self._spinner_status
            update = getattr(spinner_status, "update", None) if spinner_status else None
            if callable(update):
                try:
                    update(self._build_spinner_status_text())
                except Exception:
                    break

    def _refresh_spinner_text(self) -> None:
        spinner_status = self._spinner_status
        update = getattr(spinner_status, "update", None) if spinner_status else None
        if callable(update):
            try:
                update(self._build_spinner_status_text())
            except Exception:
                pass

    def _build_spinner_status_text(self) -> str:
        base = self._spinner_state.label or "Thinking..."
        if not self.show_elapsed_time:
            return f"[dim]{base}[/]"
        return f"[dim]{base} ({self._format_runtime_duration(self.elapsed_time)})[/]"

    @staticmethod
    def _format_runtime_duration(elapsed_seconds: float) -> str:
        total_seconds = max(0, int(elapsed_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes} min {seconds:02d}s"

    def _render_assistant_text(self, text: str, *, intermediate: bool) -> None:
        if not text.strip():
            return

        self.stop_spinner()
        text_style = "dim" if intermediate else COLORS["text_primary"]
        self._has_responded = True
        self.console.print(
            Text.assemble(
                ("DeepAgent >", f"bold {COLORS['agent']}"),
                (" ", ""),
                (text.rstrip(), text_style),
            )
        )

    def _render_tool_call(self, display_text: str) -> None:
        self.stop_spinner()
        self._has_responded = True
        self.console.print(
            f"  Tool: {escape(display_text)}",
            style=f"dim {COLORS['tool']}",
            markup=False,
        )

    def _render_tool_error(self, text: str) -> None:
        if not text:
            return
        self.stop_spinner()
        self.console.print()
        self.console.print(text, style=COLORS["error"], markup=False)
        self.console.print()

    def _render_file_operation(self, record: Any) -> None:
        from src.application.services.agent.deep.hitl.file_ops import render_file_operation

        self.stop_spinner()
        render_file_operation(record, self.console)

    def _render_elapsed(self, elapsed_time: float) -> None:
        if not self.show_elapsed_time:
            return
        self.console.print()
        self.console.print(f"Elapsed: {elapsed_time:0.1f}s", style=COLORS["text_dim"])

    def _render_summary(self, payload: Mapping[str, Any]) -> None:
        tool_calls = int(payload.get("tool_calls", 0) or 0)
        tool_names = list(payload.get("tool_names", []) or [])
        subagent_calls = list(payload.get("subagent_calls", []) or [])

        lines = ["", "Summary:"]
        if tool_calls:
            if tool_names:
                names = escape(", ".join(sorted(str(name) for name in tool_names)))
                lines.append(f"  - Tool calls: {tool_calls} ({names})")
            else:
                lines.append(f"  - Tool calls: {tool_calls}")

        if self.show_subagent_delegations and subagent_calls:
            lines.append(f"  - Subagent delegations: {len(subagent_calls)}")
            for index, call in enumerate(subagent_calls, 1):
                subagent_type = escape(str(call.get("subagent_type", "unknown")))
                description = escape(str(call.get("description", "")).strip())
                status = str(call.get("status", "") or "").strip().lower()
                status_suffix = (
                    f" ({escape(status)})"
                    if status and status not in {"delegated", "unknown"}
                    else ""
                )
                detail = f" - {description}" if description else ""
                lines.append(f"    [{index}] {subagent_type}{status_suffix}{detail}")

        if len(lines) == 2:
            return

        self.console.print("\n".join(lines))

    def _render_plain(self, text: str, style: str) -> None:
        self.console.print(text, style=style)
