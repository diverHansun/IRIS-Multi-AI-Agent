from __future__ import annotations

from typing import Any, Mapping, Protocol


class GraphBuilder(Protocol):
    """Interface for constructing executable agent graphs."""

    def add_node(self, node_id: str, definition: Mapping[str, Any]) -> None:
        """Register a node with the builder."""

    def connect(self, source_id: str, target_id: str, metadata: Mapping[str, Any] | None = None) -> None:
        """Declare a directed edge between two nodes."""

    def build(self) -> Any:
        """Finalize the graph and return the runnable artifact."""
