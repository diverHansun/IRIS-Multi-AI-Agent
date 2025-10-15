from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence


class RagNode(Protocol):
    """Interface for retrieval augmented generation nodes."""

    retriever_name: str

    def retrieve(self, query: str) -> Sequence[Any]:
        """Return ordered retrieval results for the supplied query."""

    def synthesize(self, query: str, context: Sequence[Any]) -> Mapping[str, Any]:
        """Produce model ready inputs based on the query and retrieved context."""
