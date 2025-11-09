"""Coding DeepAgent instance."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base_deep_agent import BaseDeepAgent


class CodingAgent(BaseDeepAgent):
    """Concrete DeepAgent specialized for coding tasks."""

    def __init__(
        self,
        *,
        adapter,
        runtime: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        global_memory_manager: Optional[Any] = None,
        memory_sync: Optional[Any] = None,
    ) -> None:
        base_metadata = {"capabilities": ["code_generation", "code_review", "debugging"]}
        if metadata:
            base_metadata.update(metadata)
        super().__init__(
            adapter=adapter,
            runtime=runtime,
            metadata=base_metadata,
            global_memory_manager=global_memory_manager,
            memory_sync=memory_sync,
        )
