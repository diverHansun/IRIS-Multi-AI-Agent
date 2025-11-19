from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SessionContext:
    """Represents the identity of a conversation session across engines."""

    session_id: str
    agent_type: str
    provider: str
    function_type: str = "default"
    checkpoint_id: Optional[str] = None

    def thread_id(self) -> str:
        return self.session_id or "default"

    def build_runtime_config(self, base_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Merge session routing metadata into a LangGraph runtime config.

        Note: checkpoint_ns is intentionally NOT set here.
        All modes (deep/basic/llm) share history using session_id (thread_id) only.
        This ensures conversation history persists across provider/model switches.
        LangGraph will use its default namespace handling if checkpoint_ns is not provided.
        """
        config = dict(base_config) if base_config else {}
        configurable = dict(config.get("configurable", {}))
        configurable["thread_id"] = self.thread_id()
        # Do NOT set checkpoint_ns - let LangGraph handle it with defaults
        if self.checkpoint_id:
            configurable["checkpoint_id"] = self.checkpoint_id
        config["configurable"] = configurable
        return config

    def update_checkpoint_id(self, checkpoint_id: Optional[str]) -> None:
        if checkpoint_id:
            self.checkpoint_id = checkpoint_id

