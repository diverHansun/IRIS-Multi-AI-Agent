"""Manage lifecycle of DeepAgent subagents."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SubAgentManager:
    """
    Factory for spawning and tracking subagents.

    This manager now uses SubAgentsProviderRegistry for clean parameter
    management and follows the official DeepAgents pattern for subagent creation.
    """

    def __init__(self, subagents_registry=None) -> None:
        """
        Initialize SubAgent manager.

        Args:
            subagents_registry: Optional SubAgentsProviderRegistry instance.
                If None, uses the global registry.
        """
        if subagents_registry is None:
            from src.core.providers import subagents_registry as default_registry

            subagents_registry = default_registry

        self.subagents_registry = subagents_registry
        self.active_subagents: Dict[str, Any] = {}

        logger.debug("SubAgentManager initialized with SubAgentsProviderRegistry")

    def get_available_subagents(self) -> Dict[str, Dict[str, Any]]:
        """
        Return supported subagent definitions.

        Returns:
            Dictionary mapping subagent types to their descriptions:
            {"research": {"name": "research", "description": "..."}, ...}
        """
        subagent_types = self.subagents_registry.get_available_subagents()
        result = {}

        for subagent_type in subagent_types:
            try:
                config = self.subagents_registry.get_subagent_config(subagent_type)
                result[subagent_type] = {
                    "name": config["name"],
                    "description": config["description"],
                }
            except Exception as e:
                logger.warning(
                    f"Failed to load config for subagent '{subagent_type}': {e}"
                )

        return result

    def get_subagent_config(self, subagent_type: str) -> Dict[str, Any]:
        """
        Return complete subagent configuration.

        Args:
            subagent_type: Type of subagent (research, coding, analysis)

        Returns:
            Complete subagent configuration with categorized parameters

        Raises:
            ValueError: If subagent type is not found
        """
        return self.subagents_registry.get_subagent_config(subagent_type)
