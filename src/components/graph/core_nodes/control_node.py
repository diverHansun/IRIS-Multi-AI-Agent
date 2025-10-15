from __future__ import annotations

from typing import Any, Mapping, Protocol


class ControlSignal(Protocol):
    """Represents a control instruction emitted by a control node."""

    def command(self) -> str:
        """Return the control command string."""

    def arguments(self) -> Mapping[str, Any]:
        """Return structured arguments for the control command."""


class ControlNode(Protocol):
    """Interface for nodes that manage graph level control flow."""

    def evaluate(self, inputs: Mapping[str, Any]) -> ControlSignal:
        """Produce a control signal given the current execution inputs."""
