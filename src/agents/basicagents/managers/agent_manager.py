"""
Refactored AgentManager - Unified entry point for agent creation.

Simplified manager that directly calls Adapter (Factory layer removed).
Focuses on configuration resolution and routing to appropriate Adapter.

Following SOLID principles:
- SRP: Manages only agent creation workflow
- OCP: Extendable via adapter pattern
- DIP: Depends on AgentConfig and AgentAdapter abstractions
"""

import logging
import warnings
from typing import Any, Dict, List, Optional

from src.agents.basicagents.config import AgentConfig
from src.agents.basicagents.exceptions import (
    ProviderNotFoundError,
    AgentCreationError,
)
from src.core.providers import basicagents_registry
from src.components.shared.memory.unified_checkpointer import UnifiedCheckpointer

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Agent manager for BasicAgents module.

    New implementation:
    - Parses configuration once via AgentConfig
    - Routes to appropriate Adapter
    - Adapter handles full assembly
    - No Factory layer

    Responsibilities:
    - Coordinate agent creation workflow
    - Resolve configuration via AgentConfig
    - Route to correct Adapter
    """

    def __init__(self):
        """Initialize Agent Manager."""
        self.provider_registry = basicagents_registry
        logger.info("AgentManager initialized (new implementation)")

    async def create_agent(
        self,
        provider: str,
        model: Optional[str] = None,
        *,
        shared_checkpointer: Optional[UnifiedCheckpointer] = None,
        **user_params: Any,
    ):
        """
        Create Agent instance using new optimized path.

        This is the new implementation that bypasses Factory layer.

        Args:
            provider: Provider name (zhipu, openai, ollama)
            model: Model name. If None, uses default model
            **user_params: User-provided parameters to override config defaults
                - temperature: Temperature parameter
                - max_iterations: Maximum iterations
                - max_execution_time: Maximum execution time
                - enable_memory: Enable memory
                - verbose: Verbose output
                etc.

        Returns:
            Fully initialized Agent instance

        Raises:
            ProviderNotFoundError: If provider not found
            ModelNotFoundError: If model not found
            AuthenticationError: If API key not found
            ConfigurationError: If configuration invalid
            AgentCreationError: If agent creation fails

        Example:
            >>> from src.agents.basicagents.managers import agent_manager
            >>> agent = await agent_manager.create_agent(
            ...     provider="zhipu",
            ...     model="glm-4.5",
            ...     temperature=0.3,
            ... )
        """
        provider = provider.lower()

        try:
            # Step 1: Parse configuration (validates everything including API key)
            logger.info(f"Creating agent: {provider}/{model}")
            config = AgentConfig.from_registry(
                self.provider_registry,
                provider,
                model,
                **user_params
            )

            # Step 2: Create Adapter
            adapter = self._create_adapter(
                provider,
                config,
                shared_checkpointer=shared_checkpointer,
            )

            # Step 3: Adapter creates fully initialized agent
            agent = await adapter.create_agent()

            logger.info(f"Agent created successfully: {agent.__class__.__name__}")
            return agent

        except (ProviderNotFoundError, AgentCreationError) as e:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            logger.error(f"Unexpected error during agent creation: {e}", exc_info=True)
            raise AgentCreationError(
                f"Failed to create agent for {provider}/{model}: {e}"
            ) from e

    async def create_agent_legacy(
        self,
        provider: str,
        model: Optional[str] = None,
        agent_type: str = "auto",
        **user_params: Any
    ):
        """
        Create Agent instance using legacy path (DEPRECATED).

        This method maintains backward compatibility with old Factory-based approach.
        Use create_agent() instead.

        Args:
            provider: Provider name
            model: Model name
            agent_type: Agent type (not used in new implementation)
            **user_params: User parameters

        Returns:
            Initialized Agent instance

        Deprecated:
            Use create_agent() instead. This method will be removed in future versions.
        """
        warnings.warn(
            "create_agent_legacy() is deprecated. Use create_agent() instead. "
            "Legacy path will be removed in v5.0.",
            DeprecationWarning,
            stacklevel=2
        )

        # Call new implementation
        return await self.create_agent(provider, model, **user_params)

    def _create_adapter(
        self,
        provider: str,
        config: AgentConfig,
        *,
        shared_checkpointer: Optional[UnifiedCheckpointer] = None,
    ):
        """
        Create appropriate Adapter for provider.

        Args:
            provider: Provider name
            config: Resolved AgentConfig

        Returns:
            Adapter instance

        Raises:
            ProviderNotFoundError: If no adapter found for provider
        """
        from src.agents.basicagents.adapters.zhipu_agent_adapter import ZhipuAgentAdapter
        from src.agents.basicagents.adapters.openai_agent_adapter import OpenAIAgentAdapter

        # Adapter mapping
        adapter_map = {
            "zhipu": ZhipuAgentAdapter,
            "openai": OpenAIAgentAdapter,
        }

        adapter_class = adapter_map.get(provider)
        if not adapter_class:
            available_providers = list(adapter_map.keys())
            raise ProviderNotFoundError(provider, available_providers)

        logger.debug(f"Creating {adapter_class.__name__} for {provider}")
        return adapter_class(config=config, shared_checkpointer=shared_checkpointer)

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """
        Get list of available agents.

        Returns:
            List of available agents with provider, model, agent_type info
        """
        agents = []

        # Get all provider configurations from BasicAgents registry
        all_providers = self.provider_registry.list_providers()
        for provider_key, provider_config in all_providers.items():
            provider = provider_key.lower()
            models = provider_config.get("models", {})

            # Iterate through model configurations
            for model_name, model_config in models.items():
                agent_type = model_config.get("agent_type", "react")

                agents.append({
                    "provider": provider,
                    "model": model_name,
                    "agent_type": agent_type,
                    "supports_tools": model_config.get("supports_tools", False),
                    "recommended": model_config.get("recommended", False),
                    "description": model_config.get("description", ""),
                })

        return agents


# Global Agent manager instance
agent_manager = AgentManager()


# Convenience function
async def create_agent(provider: str, model: Optional[str] = None, **kwargs):
    """
    Convenience function to create Agent instance.

    Args:
        provider: Provider name
        model: Model name
        **kwargs: Other parameters

    Returns:
        Agent instance
    """
    return await agent_manager.create_agent(provider, model, **kwargs)


def get_available_agents() -> List[Dict[str, Any]]:
    """Convenience function to get available agent list."""
    return agent_manager.get_available_agents()
