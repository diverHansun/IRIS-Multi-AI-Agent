"""
DeepAgentManager - orchestrates creation of deep agents via factories and adapters.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.agents.deepagents.factories.registry import DeepAgentFactoryRegistry
from src.agents.deepagents.managers.subagent_manager import SubAgentManager
from src.core.providers import deepagents_provider_registry

logger = logging.getLogger(__name__)


class DeepAgentManager:
    """Manage lifecycle of deep agents using factory registry."""

    def __init__(self) -> None:
        self.provider_registry = deepagents_provider_registry
        self.factory_registry = DeepAgentFactoryRegistry()
        self.subagent_manager = SubAgentManager()
        self.current_agent = None
        self.current_function: Optional[str] = None
        logger.info("DeepAgentManager initialized")

    async def create_agent(
        self,
        *,
        provider: str,
        model: Optional[str] = None,
        function: str = "research",
        deep_checkpointer: Any = None,
        middleware_config: Optional[dict] = None,
        **user_params: Any,
    ):
        """
        Create a deep agent instance using the registered factory/adapter.
        """
        function_type = function or "research"

        # Resolve provider/model
        providers = self.provider_registry.list_providers()
        provider_key = provider.lower()
        provider_cfg = providers.get(provider_key)
        if not provider_cfg:
            raise ValueError(f"Provider '{provider}' not found in deep agent config")

        models_cfg = provider_cfg.get("models", {})
        if not models_cfg:
            raise ValueError(f"Provider '{provider}' has no models configured")
        if model is None:
            model = next(iter(models_cfg.keys()))
        elif model not in models_cfg:
            logger.warning(
                "Model '%s' is not registered for provider '%s'; runtime parameters will inherit provider defaults.",
                model,
                provider,
            )

        # Resolve factory and adapter
        factory = self.factory_registry.get_factory(function_type)
        adapter_cls = self.factory_registry.get_adapter_class(function_type)
        if not factory or not adapter_cls:
            raise ValueError(f"Unsupported deep agent function '{function_type}'")

        adapter = adapter_cls(
            provider=provider,
            model=model,
            provider_registry=self.provider_registry,
        )

        # Middleware: use registry defaults if not provided
        middleware_cfg = middleware_config or self.provider_registry.get_middleware_config()

        agent = await factory.create_agent(
            provider=provider,
            model=model,
            adapter=adapter,
            subagent_manager=self.subagent_manager,
            middleware_config=middleware_cfg,
            deep_checkpointer=deep_checkpointer,
            **user_params,
        )

        self.current_agent = agent
        self.current_function = function_type
        return agent

    async def create_deep_agent(
        self,
        provider: str,
        model: Optional[str] = None,
        function_type: str = "research",
        deep_checkpointer: Any = None,
        **user_params: Any,
    ):
        """Alias used by callers."""
        return await self.create_agent(
            provider=provider,
            model=model,
            function=function_type,
            deep_checkpointer=deep_checkpointer,
            **user_params,
        )

    def get_available_functions(self):
        return list(self.factory_registry.describe_factories().keys())


# Global manager instance
deep_agent_manager = DeepAgentManager()


async def create_deep_agent(
    provider: str,
    model: Optional[str] = None,
    function_type: str = "research",
    deep_checkpointer: Any = None,
    **kwargs: Any,
):
    """Convenience wrapper."""
    return await deep_agent_manager.create_deep_agent(
        provider=provider,
        model=model,
        function_type=function_type,
        deep_checkpointer=deep_checkpointer,
        **kwargs,
    )
