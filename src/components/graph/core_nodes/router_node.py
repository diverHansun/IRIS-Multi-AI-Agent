from __future__ import annotations

from typing import Any, Mapping, Protocol


class RouterDecision(Protocol):
    """Represents a routing decision returned by a router node."""

    def target(self) -> str:
        """Return the next node identifier."""

    def payload(self) -> Mapping[str, Any]:
        """Return structured arguments for the next node."""


class RouterNode(Protocol):
    """Interface for nodes that choose the next execution path."""

    def route(self, inputs: Mapping[str, Any]) -> RouterDecision:
        """Select the next node based on the incoming payload."""
