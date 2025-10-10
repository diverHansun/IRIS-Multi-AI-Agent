"""
Agent Factories

抽象工厂模式实现，用于创建不同Provider的Agent。
"""

from .base import BaseAgentFactory
from .zhipu_factory import ZhipuAgentFactory
from .openai_factory import OpenAIAgentFactory
from .ollama_factory import OllamaAgentFactory
from .registry import FactoryRegistry, get_global_registry, reset_global_registry

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
]
