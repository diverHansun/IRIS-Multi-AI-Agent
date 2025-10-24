"""Subagent middleware management for deep agents."""

from __future__ import annotations

from typing import Any, Dict

from src.agents.deepagents.managers import subagent_manager


class SubagentsMiddlewareService:
    """Expose subagent configuration and status."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        config = config or {}
        self.enabled: bool = bool(config.get("enabled", True))
        self.max_concurrent: int = int(config.get("max_concurrent", 3))
        self.timeout: int = int(config.get("timeout", 300))
        self.config = config

    def describe(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_concurrent": self.max_concurrent,
            "timeout": self.timeout,
            "available_subagents": list(subagent_manager.get_available_subagents().keys()),
            "configuration": self.config.get("subagents", {}),
        }
