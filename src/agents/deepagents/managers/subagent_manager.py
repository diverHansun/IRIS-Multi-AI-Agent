"""
SubagentManager - Manager for subagent instances.

Backed by SubAgentsProviderRegistry to supply real subagent configs to
factories and middleware.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.core.providers.subagents_provider_registry import subagents_registry

logger = logging.getLogger(__name__)


class SubagentManager:
    """
    Manage configured subagents and track active ones.
    """

    def __init__(self):
        self.active_subagents: Dict[str, Any] = {}
        self.subagents_registry = subagents_registry
        logger.info("SubagentManager initialized")

    async def create_subagent(
        self,
        subagent_type: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **user_params: Any,
    ):
        """
        Minimal creation stub: resolve config and record activation.
        """
        config = self.get_subagent_config(subagent_type)
        self.active_subagents[subagent_type] = {
            "provider": provider or config["llm_config"]["provider"],
            "model": model or config["llm_config"]["model"],
            "params": user_params,
        }
        return config

    def get_active_subagents(self) -> Dict[str, Any]:
        """Return a copy of currently active subagents."""
        return self.active_subagents.copy()

    def get_available_types(self) -> List[str]:
        """List available subagent types from registry."""
        return self.subagents_registry.get_available_subagents()

    def get_available_subagents(self) -> Dict[str, Any]:
        """Return available subagent configs keyed by type."""
        return {
            sub: self.subagents_registry.get_subagent_config(sub)
            for sub in self.subagents_registry.get_available_subagents()
        }

    def get_subagent_config(self, subagent_type: str) -> Dict[str, Any]:
        """Return full configuration for a subagent type."""
        return self.subagents_registry.get_subagent_config(subagent_type)


# Global Subagent manager instance
subagent_manager = SubagentManager()


# Convenience function
async def create_subagent(
    subagent_type: str,
    provider: str,
    model: Optional[str] = None,
    **kwargs,
):
    return await subagent_manager.create_subagent(subagent_type, provider, model, **kwargs)


# Backward-compatible alias used by factories
class SubAgentManager(SubagentManager):
    pass
