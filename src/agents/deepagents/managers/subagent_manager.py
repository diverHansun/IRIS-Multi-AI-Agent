"""Manage lifecycle of DeepAgent subagents."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SubAgentManager:
    """Factory for spawning and tracking subagents."""

    def __init__(self, provider_registry: Optional[Any] = None) -> None:
        if provider_registry is None:
            from src.core.providers import deepagents_provider_registry

            provider_registry = deepagents_provider_registry

        self.provider_registry = provider_registry
        self.models_config = provider_registry.get_models_config()
        self.active_subagents: Dict[str, Any] = {}

    async def create_subagent(
        self,
        subagent_type: str,
        task_description: str,
        *,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create a subagent based on configuration."""
        config = self._resolve_subagent_config(subagent_type)
        params = {**config, "task_description": task_description}
        if overrides:
            params.update(overrides)

        provider = params.pop("provider")
        model = params.pop("model")
        agent_type = params.pop("agent_type", "basic")

        logger.debug(
            "Spawning subagent type=%s provider=%s model=%s",
            subagent_type,
            provider,
            model,
        )

        from src.agents.basicagents.managers import agent_manager

        agent = await agent_manager.create_agent(
            provider=provider,
            model=model,
            agent_type=agent_type,
            **params,
        )
        self.active_subagents[subagent_type] = agent
        return agent

    def get_available_subagents(self) -> Dict[str, Dict[str, Any]]:
        """Return supported subagent definitions."""
        # models_config is already the subagents dict from subagents.json
        # Structure: {"research": {...}, "coding": {...}, "analysis": {...}}
        return self.models_config if self.models_config else {}

    def get_subagent_config(self, subagent_type: str) -> Dict[str, Any]:
        """Return resolved provider/model configuration for a subagent."""
        return self._resolve_subagent_config(subagent_type)

    def _resolve_subagent_config(self, subagent_type: str) -> Dict[str, Any]:
        """Fetch configuration for a subagent type."""
        # models_config is already the subagents dict
        config = self.models_config.get(subagent_type)
        if not config:
            msg = f"Unknown subagent type: {subagent_type}"
            logger.error(msg)
            raise ValueError(msg)

        # Flatten provider/model selection: choose first provider/model pair
        providers = config.get("providers", {})
        if not providers:
            msg = f"No providers configured for subagent type: {subagent_type}"
            logger.error(msg)
            raise ValueError(msg)

        provider_name, provider_cfg = next(iter(providers.items()))
        models = provider_cfg.get("models", {})
        if not models:
            msg = f"No models configured for subagent type: {subagent_type}"
            logger.error(msg)
            raise ValueError(msg)

        model_name, model_cfg = next(iter(models.items()))
        resolved = {
            "provider": provider_name,
            "model": model_name,
        }
        resolved.update(model_cfg)
        return resolved
