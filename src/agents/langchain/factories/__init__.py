"""
Agent Factories

Factory pattern implementation for creating Agents from different providers.
"""

import warnings
from typing import Dict, Any

from .base import BaseAgentFactory
from .zhipu_factory import ZhipuAgentFactory
from .openai_factory import OpenAIAgentFactory
from .ollama_factory import OllamaAgentFactory
from .registry import (
    FactoryRegistry,
    get_global_registry,
    reset_global_registry,
)

# Backward compatible: provide agent_factory alias
agent_factory = get_global_registry()


# Compatibility functions (deprecated in v4.0, will be removed in v5.0)

async def create_agent(provider: str, model: str = None, **kwargs):
    """
    .. deprecated:: 4.0
        Use agent_manager.create_agent() instead.
        This function will be removed in v5.0.
    """
    warnings.warn(
        "create_agent from factories is deprecated. "
        "Use agent_manager.create_agent() instead. "
        "Will be removed in v5.0.",
        DeprecationWarning,
        stacklevel=2
    )
    from src.agents.langchain.managers import agent_manager
    return await agent_manager.create_agent(provider, model, **kwargs)


async def create_default_agent(**kwargs):
    """
    .. deprecated:: 4.0
        Use agent_manager.create_agent("zhipu", None) instead.
        This function will be removed in v5.0.
    """
    warnings.warn(
        "create_default_agent is deprecated. "
        "Use agent_manager.create_agent('zhipu', None) instead. "
        "Will be removed in v5.0.",
        DeprecationWarning,
        stacklevel=2
    )
    from src.agents.langchain.managers import agent_manager
    return await agent_manager.create_agent("zhipu", None, **kwargs)


def get_available_configurations() -> Dict[str, Any]:
    """
    .. deprecated:: 4.0
        Use agent_manager.get_available_agents() instead.
        This function will be removed in v5.0.
    """
    warnings.warn(
        "get_available_configurations is deprecated. "
        "Use agent_manager.get_available_agents() instead. "
        "Will be removed in v5.0.",
        DeprecationWarning,
        stacklevel=2
    )
    from src.agents.langchain.managers import agent_manager
    return {"available_agents": agent_manager.get_available_agents()}


__all__ = [
    # Base
    "BaseAgentFactory",

    # Concrete Factories
    "ZhipuAgentFactory",
    "OpenAIAgentFactory",
    "OllamaAgentFactory",

    # Registry
    "FactoryRegistry",
    "get_global_registry",
    "reset_global_registry",

    # Backward compatible alias
    "agent_factory",

    # Compatibility functions (deprecated)
    "create_agent",
    "create_default_agent",
    "get_available_configurations",
]
