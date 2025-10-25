"""Base class for agent adapters.

Responsible for resolving provider configuration, preparing parameters,
and creating LLM instances for agents.

Following SOLID principles:
- SRP: Manages agent configuration and LLM creation
- OCP: Extendable via subclasses
- DIP: Depends on BasicAgentsProviderRegistry abstraction
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Sequence

from langgraph.graph.state import CompiledStateGraph

from src.core.providers.basicagents_provider_registry import (
    BasicAgentsProviderRegistry,
    basicagents_registry as default_registry,
)

logger = logging.getLogger(__name__)


class AgentAdapter(ABC):
    """
    Base class for agent parameter adapters.

    Responsibilities:
    - Load and manage agent configuration from BasicAgentsProviderRegistry
    - Create LLM instances with complete configuration
    - Provide agent-specific parameters
    - Create agent graphs
    """

    def __init__(
        self,
        provider: str,
        model: Optional[str],
        provider_registry: Optional[BasicAgentsProviderRegistry] = None,
    ):
        """
        Initialize agent adapter.

        Args:
            provider: Provider name
            model: Model name. If None, uses default model
            provider_registry: Optional custom registry instance
        """
        self.provider_registry = provider_registry or default_registry
        self.provider = provider.lower()

        # Get complete agent configuration
        try:
            self._config = self.provider_registry.get_agent_config(
                self.provider, model
            )
            self.model = self._config["model"]
        except ValueError as e:
            logger.error(f"Failed to initialize agent adapter: {e}")
            raise

        logger.debug(
            "Agent adapter initialized: provider=%s model=%s",
            self.provider,
            self.model,
        )

    def get_agent_params(self, **user_params: Any) -> Dict[str, Any]:
        """
        Get agent parameters with user overrides.

        Args:
            **user_params: User-provided parameter overrides

        Returns:
            Merged agent parameters dict
        """
        params = {
            "agent_type": self._config.get("agent_type", "react"),
            "max_iterations": self._config.get("max_iterations", 8),
            "max_execution_time": self._config.get("max_execution_time", 300),
            "memory_enabled": self._config.get("memory_enabled", True),
        }

        # Apply user overrides
        for key, value in user_params.items():
            if value is not None:
                params[key] = value

        logger.debug(
            "Resolved agent params for %s/%s: %s",
            self.provider,
            self.model,
            params,
        )
        return params

    def create_llm(self, **user_params: Any) -> Any:
        """
        Create LLM instance using complete agent configuration.

        Configuration priority: user_params > env vars > config file

        Args:
            **user_params: User-provided parameter overrides

        Returns:
            LangChain compatible LLM instance

        Raises:
            ValueError: If API key not found or configuration invalid
        """
        # Get API key from environment
        api_key_env = self._config.get("api_key_env")
        if api_key_env:
            api_key = os.getenv(api_key_env)
            if not api_key:
                raise ValueError(
                    f"API key not found in environment variable: {api_key_env}"
                )
        else:
            api_key = None  # For providers that don't need API key (e.g., Ollama)

        # Get base_url (priority: user_params > env > config)
        base_url = (
            user_params.get("base_url")
            or self._config.get("base_url")
        )

        # Build LLM parameters
        llm_params = {
            "model": self.model,
            "temperature": self._config.get("temperature", 0.1),
            "max_tokens": self._config.get("max_tokens"),
            "streaming": self._config.get("streaming", False),
        }

        # Apply user overrides for LLM params
        for key in ["temperature", "max_tokens", "streaming"]:
            if key in user_params and user_params[key] is not None:
                llm_params[key] = user_params[key]

        # Provider-specific LLM creation
        return self._create_llm_instance(
            api_key=api_key,
            base_url=base_url,
            llm_params=llm_params,
            user_params=user_params,
        )

    @abstractmethod
    def _create_llm_instance(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        llm_params: Dict[str, Any],
        user_params: Dict[str, Any],
    ) -> Any:
        """
        Create provider-specific LLM instance.

        Subclasses must implement this method to create their specific LLM client.

        Args:
            api_key: Resolved API key
            base_url: Resolved base URL
            llm_params: LLM parameters (temperature, max_tokens, etc.)
            user_params: Additional user parameters

        Returns:
            LangChain compatible LLM instance
        """
        pass

    @abstractmethod
    def create_agent_graph(
        self,
        llm: Any,
        tools: Sequence[Any],
        *,
        checkpointer: Optional[Any] = None,
        **params: Any,
    ) -> CompiledStateGraph:
        """
        Create a CompiledStateGraph using the prepared parameters.

        Args:
            llm: LLM instance
            tools: List of tools
            checkpointer: Optional checkpointer for memory
            **params: Additional parameters

        Returns:
            CompiledStateGraph instance
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """
        Return metadata for the associated model.

        Returns:
            Model information dict
        """
        return {
            "provider": self.provider.lower(),
            "model": self.model,
            "agent_type": self._config.get("agent_type", "react"),
            "supports_tools": self._config.get("supports_tools", False),
            "max_tokens": self._config.get("max_tokens"),
            "context_window": self._config.get("context_window"),
            "max_iterations": self._config.get("max_iterations", 8),
            "max_execution_time": self._config.get("max_execution_time", 300),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider}, model={self.model})"
