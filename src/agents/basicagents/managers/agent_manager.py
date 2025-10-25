"""
Agent Manager - Unified entry point for agent creation and management.

Responsible for coordinating agent creation and applying configuration parameters.

Following SOLID principles:
- SRP: Manages only agent creation workflow
- OCP: Extendable via factory pattern
- DIP: Depends on BasicAgentsProviderRegistry abstraction
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Agent manager for BasicAgents module.

    Responsibilities:
    - Coordinate agent creation workflow
    - Integrate Agent Adapter and Factory
    - Apply agent configuration parameters
    """

    def __init__(self):
        """Initialize Agent Manager."""
        from src.core.providers import basicagents_registry
        from src.agents.basicagents.factories.registry import FactoryRegistry

        self.provider_registry = basicagents_registry
        self.factory_registry = FactoryRegistry()

        logger.info("AgentManager initialized")

    async def create_agent(
        self,
        provider: str,
        model: str = None,
        agent_type: str = "auto",
        **user_params
    ):
        """
        Create Agent instance.

        Args:
            provider: Provider name (zhipu, openai, ollama)
            model: Model name. If None, uses default model
            agent_type: Agent type ("auto", "react", "function_calling")
            **user_params: User-provided parameters to override config defaults
                - temperature: Temperature parameter
                - max_iterations: Maximum iterations
                - max_execution_time: Maximum execution time
                - enable_memory: Enable memory
                - verbose: Verbose output
                etc.

        Returns:
            Initialized Agent instance

        Example:
            >>> from src.agents.basicagents.managers import agent_manager
            >>> agent = await agent_manager.create_agent(
            ...     provider="zhipu",
            ...     model="glm-4.5",
            ...     verbose=True
            ... )
        """
        provider = provider.lower()

        # Get provider configuration to resolve default model
        provider_config = self._get_provider_config(provider)
        if not model:
            model = provider_config.get("default_model")

        logger.info(f"Creating agent: {provider}/{model}")

        # Create Agent Adapter (includes LLM creation capability)
        agent_adapter = self._create_agent_adapter(provider, model)

        # Create LLM using agent adapter
        llm = agent_adapter.create_llm(**user_params)

        # Get Factory and create Agent
        factory = self.factory_registry.get_factory(provider)
        if not factory:
            raise ValueError(f"No factory found for provider: {provider}")

        # Use Factory to create Agent
        agent = await factory.create_agent_with_adapters(
            model=model,
            llm_adapter=None,  # No longer needed, adapter creates LLM directly
            agent_adapter=agent_adapter,
            llm=llm,  # Pass created LLM directly
            **user_params
        )

        logger.info(f"Agent created: {agent.__class__.__name__}")
        return agent

    def _get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get provider configuration.

        Args:
            provider: Provider name

        Returns:
            Provider configuration dict

        Raises:
            ValueError: If provider not found
        """
        try:
            config = self.provider_registry.get_provider_config(provider)
            if not config:
                raise ValueError(f"Provider {provider} not found")
            return config
        except Exception as e:
            logger.error(f"Failed to get provider config: {e}")
            raise

    def _create_agent_adapter(self, provider: str, model: str):
        """
        Create Agent adapter.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Agent adapter instance

        Raises:
            ValueError: If no adapter found for provider
        """
        from src.agents.basicagents.adapters import (
            ZhipuAgentAdapter,
            OpenAIAgentAdapter,
            OllamaAgentAdapter,
        )

        adapter_map = {
            "zhipu": ZhipuAgentAdapter,
            "openai": OpenAIAgentAdapter,
            "ollama": OllamaAgentAdapter,
        }

        adapter_class = adapter_map.get(provider)
        if not adapter_class:
            raise ValueError(f"No Agent adapter found for provider: {provider}")

        return adapter_class(
            model=model,
            provider_registry=self.provider_registry,
        )

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

            # For Ollama, dynamically detect available local models
            if provider == "ollama":
                try:
                    import asyncio
                    from src.core.providers.utils import list_ollama_models

                    # Check if already in event loop
                    try:
                        loop = asyncio.get_running_loop()
                        # If in event loop, create new thread to run async function
                        import concurrent.futures

                        def run_async():
                            return asyncio.run(list_ollama_models())

                        # Run async function in new thread
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(run_async)
                            local_models = future.result(timeout=10)
                    except RuntimeError:
                        # No running event loop, run directly
                        local_models = asyncio.run(list_ollama_models())

                    # Create agent entry for each local model
                    for model_name in local_models:
                        agents.append({
                            "provider": provider,
                            "model": model_name,
                            "agent_type": "react",
                            "supports_tools": True,
                            "recommended": True,
                            "description": f"Ollama local model: {model_name}",
                        })

                    # If no local models, add placeholder entry
                    if not local_models:
                        agents.append({
                            "provider": provider,
                            "model": "default",
                            "agent_type": "react",
                            "supports_tools": True,
                            "recommended": False,
                            "description": "Ollama local model (no models available)",
                        })
                except Exception as e:
                    logger.warning(f"Failed to get Ollama model list: {e}")
                    # Add basic Ollama entry even if can't get specific models
                    agents.append({
                        "provider": provider,
                        "model": "unknown",
                        "agent_type": "react",
                        "supports_tools": True,
                        "recommended": False,
                        "description": "Ollama local model service",
                    })
            else:
                # For other providers, use predefined model list
                for model_name, model_config in models.items():
                    # Determine agent type from config
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


# Convenience functions
async def create_agent(provider: str, model: str = None, **kwargs):
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
