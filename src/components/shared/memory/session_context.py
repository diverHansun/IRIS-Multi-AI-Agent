from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


def _sanitize(value: str) -> str:
    """Normalize namespace components for checkpoint usage."""
    if not value:
        return "default"
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value.lower().strip())


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

    def checkpoint_namespace(self) -> str:
        return f"{_sanitize(self.agent_type)}::{_sanitize(self.provider)}::{_sanitize(self.function_type)}"

    def build_runtime_config(self, base_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Merge session routing metadata into a LangGraph runtime config."""
        config = dict(base_config) if base_config else {}
        configurable = dict(config.get("configurable", {}))
        configurable["thread_id"] = self.thread_id()
        configurable["checkpoint_ns"] = self.checkpoint_namespace()
        if self.checkpoint_id:
            configurable["checkpoint_id"] = self.checkpoint_id
        config["configurable"] = configurable
        return config

    def update_checkpoint_id(self, checkpoint_id: Optional[str]) -> None:
        if checkpoint_id:
            self.checkpoint_id = checkpoint_id

