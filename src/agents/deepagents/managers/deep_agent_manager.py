"""Manager responsible for DeepAgent lifecycle orchestration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.agents.deepagents.factories.registry import DeepAgentFactoryRegistry
from src.agents.deepagents.adapters.base import BaseDeepAgentAdapter

logger = logging.getLogger(__name__)


class DeepAgentManager:
    """Coordinate DeepAgent creation across providers and function types."""

    def __init__(self, subagent_manager: Optional["SubAgentManager"] = None) -> None:
        from src.core.providers import deepagents_provider_registry
        from .subagent_manager import SubAgentManager

        self.provider_registry = deepagents_provider_registry
        self.factory_registry = DeepAgentFactoryRegistry()
        self.subagent_manager = subagent_manager or SubAgentManager()

        logger.debug("DeepAgentManager initialized")

    async def create_deep_agent(
        self,
        provider: str,
        model: str,
        *,
        function_type: str = "research",
        global_memory_manager: Optional[Any] = None,
        **user_params: Any,
    ) -> Any:
        """Create a DeepAgent instance for the requested function type."""
        provider_key = provider.lower()
        function_type = user_params.pop("function_type", function_type)

        # Extract global_memory_manager from user_params if provided there
        if global_memory_manager is None:
            global_memory_manager = user_params.pop("global_memory_manager", None)

        logger.info("Creating deep agent for provider=%s model=%s function=%s", provider_key, model, function_type)

        provider_config, resolved_model = self._get_provider_config(provider_key, model)
        logger.info(
            "Creating deep agent for provider=%s model=%s function=%s",
            provider_key,
            resolved_model,
            function_type,
        )
        adapter = self._create_agent_adapter(function_type, provider_key, resolved_model, provider_config)
        middleware_config = self.provider_registry.get_middleware_config()

        factory = self.factory_registry.get_factory(function_type)
        if not factory:
            msg = f"No deep agent factory registered for function type '{function_type}'"
            logger.error(msg)
            raise ValueError(msg)

        # Pass global_memory_manager to factory
        agent = await factory.create_agent(
            provider=provider_key,
            model=resolved_model,
            adapter=adapter,
            subagent_manager=self.subagent_manager,
            provider_config=provider_config,
            middleware_config=middleware_config,
            global_memory_manager=global_memory_manager,
            **user_params,
        )

        logger.info("Deep agent created: %s", agent.__class__.__name__)
        return agent

    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        """Return metadata about registered deep agent functions."""
        return self.factory_registry.describe_factories()

    def _get_provider_config(self, provider: str, model: Optional[str]) -> tuple[Dict[str, Any], str]:
        """Safely resolve provider configuration."""
        providers = self.provider_registry.list_providers()
        provider_entry = providers.get(provider)
        if provider_entry is None:
            raise ValueError(f"Provider {provider} not configured for deep agents.")

        models = provider_entry.get("models", {})
        if not models:
            raise ValueError(f"No models configured for provider {provider}.")

        resolved_model = model or next(iter(models.keys()))
        if resolved_model not in models:
            raise ValueError(f"Model {resolved_model} not found for provider {provider}.")

        config = self.provider_registry.get_deep_agent_config(provider, resolved_model)
        return config, resolved_model

    def _create_agent_adapter(
        self,
        function_type: str,
        provider: str,
        model: str,
        provider_config: Dict[str, Any],
    ) -> BaseDeepAgentAdapter:
        """Instantiate the adapter for the requested function."""
        adapter_cls = self.factory_registry.get_adapter_class(function_type)
        if not adapter_cls:
            msg = f"No adapter registered for function type '{function_type}'"
            logger.error(msg)
            raise ValueError(msg)

        adapter = adapter_cls(
            provider=provider,
            model=model,
            provider_config=provider_config,
        )
        logger.debug(
            "Adapter instantiated for provider=%s model=%s function=%s",
            provider,
            model,
            function_type,
        )
        return adapter


# Avoid circular import issues in type hints
from .subagent_manager import SubAgentManager  # noqa: E402  (import at end for MYPY)
