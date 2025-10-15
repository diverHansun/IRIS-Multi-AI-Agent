from __future__ import annotations

from typing import Any, Mapping, Protocol


class MemoryNode(Protocol):
    """Interface for nodes that provide shared state read and write semantics."""

    def read(self, key: str) -> Any:
        """Fetch a value from graph scoped memory."""

    def write(self, key: str, value: Any) -> None:
        """Persist a value into graph scoped memory."""

    def snapshot(self) -> Mapping[str, Any]:
        """Return a serializable copy of the memory contents."""
