from __future__ import annotations

from typing import Any, Mapping, Protocol


class CheckpointNode(Protocol):
    """Interface for nodes that persist and restore execution state."""

    def save(self, state: Mapping[str, Any]) -> None:
        """Persist the supplied execution state."""

    def load(self) -> Mapping[str, Any]:
        """Restore a previously saved execution state."""
