"""
Agent Factories

Factory pattern implementation for creating Agents from different providers.
"""

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
]
