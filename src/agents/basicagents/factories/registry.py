"""
Agent Factory Registry

Simplified factory registry for managing and locating Agent factories.
Responsibilities: Register + Lookup + Cache only.
"""

import logging
from typing import Dict, Optional, Any, List

from .base import BaseAgentFactory
from .zhipu_factory import ZhipuAgentFactory
from .openai_factory import OpenAIAgentFactory
from .ollama_factory import OllamaAgentFactory

logger = logging.getLogger(__name__)


class FactoryRegistry:
    """
    Agent Factory Registry (Simplified)

    Responsibilities:
    - Register factories
    - Lookup factories
    - Cache agents (optional)
    """

    def __init__(self, auto_register_defaults: bool = True):
        """
        Initialize factory registry

        Args:
            auto_register_defaults: Whether to auto-register default factories
        """
        self._factories: Dict[str, BaseAgentFactory] = {}
        self._agent_cache: Dict[str, Any] = {}

        if auto_register_defaults:
            self._register_default_factories()

    def _register_default_factories(self) -> None:
        """Register default factories"""
        self.register_factory("zhipu", ZhipuAgentFactory())
        self.register_factory("openai", OpenAIAgentFactory())
        self.register_factory("ollama", OllamaAgentFactory())
        logger.debug("Registered default Agent factories: zhipu, openai, ollama")

    def register_factory(self, provider: str, factory: BaseAgentFactory) -> None:
        """
        Register a factory

        Args:
            provider: Provider name
            factory: Factory instance
        """
        provider_key = provider.lower()
        self._factories[provider_key] = factory
        logger.debug(f"Registered Agent factory: {provider_key} -> {factory.__class__.__name__}")

    def get_factory(self, provider: str) -> Optional[BaseAgentFactory]:
        """
        Get factory by provider name

        Args:
            provider: Provider name

        Returns:
            Factory instance or None if not found
        """
        provider_key = provider.lower()
        factory = self._factories.get(provider_key)

        if factory is None:
            logger.warning(f"Factory not found for provider: {provider_key}")

        return factory

    def has_factory(self, provider: str) -> bool:
        """
        Check if factory exists

        Args:
            provider: Provider name

        Returns:
            True if factory exists
        """
        return provider.lower() in self._factories

    def list_providers(self) -> List[str]:
        """List all registered providers"""
        return list(self._factories.keys())

    def get_cached_agent(self, cache_key: str) -> Optional[Any]:
        """Get cached agent"""
        return self._agent_cache.get(cache_key)

    def set_cached_agent(self, cache_key: str, agent: Any) -> None:
        """Cache an agent"""
        self._agent_cache[cache_key] = agent

    def clear_cache(self) -> None:
        """Clear agent cache"""
        self._agent_cache.clear()
        logger.info("Cleared agent cache")

    def __repr__(self) -> str:
        providers = ', '.join(self._factories.keys())
        return f"FactoryRegistry(providers=[{providers}])"


# Global singleton
_global_registry: Optional[FactoryRegistry] = None


def get_global_registry() -> FactoryRegistry:
    """
    Get global factory registry singleton

    Returns:
        Global FactoryRegistry instance
    """
    global _global_registry

    if _global_registry is None:
        _global_registry = FactoryRegistry(auto_register_defaults=True)
        logger.debug("Created global Agent factory registry")

    return _global_registry


def reset_global_registry() -> None:
    """Reset global factory registry (mainly for testing)"""
    global _global_registry
    _global_registry = None
    logger.debug("Reset global Agent factory registry")
