from __future__ import annotations

from typing import Any, Mapping, Protocol


class ToolNode(Protocol):
    """Interface for nodes that execute an atomic tool operation."""

    name: str

    def run(self, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        """Execute the tool using structured inputs and return structured outputs."""
