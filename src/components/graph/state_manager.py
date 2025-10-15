from __future__ import annotations

from typing import Any, Mapping, Protocol


class GraphStateManager(Protocol):
    """Interface for managing execution state across graph runs."""

    def load(self, key: str) -> Mapping[str, Any] | None:
        """Retrieve persisted state for the supplied key."""

    def save(self, key: str, state: Mapping[str, Any]) -> None:
        """Persist state under the supplied key."""

    def clear(self, key: str) -> None:
        """Remove persisted state for the supplied key."""
