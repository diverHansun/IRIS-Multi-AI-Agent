"""Research DeepAgent instance."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base_deep_agent import BaseDeepAgent


class ResearchAgent(BaseDeepAgent):
    """Concrete DeepAgent specialized for research tasks."""

    def __init__(
        self,
        *,
        adapter,
        runtime: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        base_metadata = {"capabilities": ["research", "analysis", "synthesis"]}
        if metadata:
            base_metadata.update(metadata)
        super().__init__(adapter=adapter, runtime=runtime, metadata=base_metadata)
