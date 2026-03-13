"""Semantic spinner state models for terminal transcript renderers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Literal


SpinnerKind = Literal[
    "idle",
    "thinking",
    "tool_calling",
    "subagent_running",
    "file_activity",
    "hitl_waiting",
]


@dataclass(frozen=True, slots=True)
class SpinnerState:
    """Describe a semantic terminal spinner state."""

    kind: SpinnerKind
    payload: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def idle(cls) -> "SpinnerState":
        return cls(kind="idle")

    @classmethod
    def thinking(cls) -> "SpinnerState":
        return cls(kind="thinking")

    @classmethod
    def tool_calling(cls, tool_name: str | None = None) -> "SpinnerState":
        payload = {"tool_name": tool_name} if tool_name else {}
        return cls(kind="tool_calling", payload=payload)

    @classmethod
    def subagent_running(cls, subagent_type: str | None = None) -> "SpinnerState":
        payload = {"subagent_type": subagent_type} if subagent_type else {}
        return cls(kind="subagent_running", payload=payload)

    @classmethod
    def file_activity(cls, action: str | None = None) -> "SpinnerState":
        payload = {"action": action} if action else {}
        return cls(kind="file_activity", payload=payload)

    @classmethod
    def hitl_waiting(cls) -> "SpinnerState":
        return cls(kind="hitl_waiting")

    @property
    def visible(self) -> bool:
        """Return whether the spinner should be shown for this state."""
        return self.kind != "idle"

    @property
    def label(self) -> str:
        """Return the user-facing label for the current state."""
        if self.kind == "thinking":
            return "Thinking..."
        if self.kind == "tool_calling":
            tool_name = str(self.payload.get("tool_name", "") or "").strip()
            return f"Calling tool {tool_name}..." if tool_name else "Calling tool..."
        if self.kind == "subagent_running":
            subagent_type = str(self.payload.get("subagent_type", "") or "").strip()
            return (
                f"Subagent {subagent_type} running..."
                if subagent_type
                else "Subagent running..."
            )
        if self.kind == "file_activity":
            action = str(self.payload.get("action", "") or "").strip()
            return f"Working with files ({action})..." if action else "Working with files..."
        if self.kind == "hitl_waiting":
            return "Waiting for approval..."
        return ""


class SpinnerStatusController:
    """Track semantic spinner state and notify a renderer on transitions."""

    def __init__(
        self,
        *,
        on_change: Callable[[SpinnerState], None] | None = None,
        initial_state: SpinnerState | None = None,
    ) -> None:
        self._state = initial_state or SpinnerState.idle()
        self._on_change = on_change

    @property
    def state(self) -> SpinnerState:
        """Return the current spinner state."""
        return self._state

    def set_state(self, state: SpinnerState) -> None:
        """Switch to a new spinner state and notify the renderer."""
        if state == self._state:
            return
        self._state = state
        if self._on_change is not None:
            self._on_change(state)

    def set_idle(self) -> None:
        self.set_state(SpinnerState.idle())

    def set_thinking(self) -> None:
        self.set_state(SpinnerState.thinking())

    def set_tool_calling(self, tool_name: str | None = None) -> None:
        self.set_state(SpinnerState.tool_calling(tool_name))

    def set_subagent_running(self, subagent_type: str | None = None) -> None:
        self.set_state(SpinnerState.subagent_running(subagent_type))

    def set_file_activity(self, action: str | None = None) -> None:
        self.set_state(SpinnerState.file_activity(action))

    def set_hitl_waiting(self) -> None:
        self.set_state(SpinnerState.hitl_waiting())
