"""
Agent Factories

抽象工厂模式实现，用于创建不同Provider的Agent。
提供便捷函数和向后兼容的agent_factory别名。
"""

from .base import BaseAgentFactory
from .zhipu_factory import ZhipuAgentFactory
from .openai_factory import OpenAIAgentFactory
from .ollama_factory import OllamaAgentFactory
from .registry import (
    FactoryRegistry,
    get_global_registry,
    reset_global_registry,
    # 便捷函数
    create_agent,
    create_default_agent,
    create_zhipu_agent,
    create_openai_agent,
    create_ollama_agent,
    get_available_configurations,
)

# 向后兼容：提供agent_factory别名
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

    # 便捷函数（NEW）
    "create_agent",
    "create_default_agent",
    "create_zhipu_agent",
    "create_openai_agent",
    "create_ollama_agent",
    "get_available_configurations",

    # 向后兼容别名（NEW）
    "agent_factory",
]
