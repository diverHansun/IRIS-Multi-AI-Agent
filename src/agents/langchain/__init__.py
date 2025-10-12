"""
智能代理模块

提供各种Agent提供商的实现。

架构说明：
- instances/: Agent具体实现（BaseAgent, ZhipuAgent, OpenAIAgent, OllamaAgent）
- factories/: 抽象工厂模式（FactoryRegistry, ZhipuFactory, OpenAIFactory, OllamaFactory）
- builders/: 建造者模式（AgentBuilder, AgentPresets）
- agent_factory.py: 统一工厂入口（内部使用Registry，保持向后兼容）
"""

# Agent Instances
from .instances import (
    BaseAgent,
    ZhipuAgent,
    build_zhipu_agent,
    ZhipuFCallAgent,
    build_zhipu_fcall_agent,
    OpenAIAgent,
    build_openai_agent,
    OllamaAgent,
    build_ollama_agent,
)

# Factory Pattern - 现在从 factories 模块导入
from .factories import (
    # Abstract Factory Pattern
    BaseAgentFactory,
    ZhipuAgentFactory,
    OpenAIAgentFactory,
    OllamaAgentFactory,
    FactoryRegistry,
    get_global_registry,
    agent_factory,
)

# 向后兼容：AgentFactory 类别名
AgentFactory = FactoryRegistry

# Builder Pattern (NEW)
from .builders import (
    AgentBuilder,
    AgentPresets,
)

__all__ = [
    # Agent instances
    "BaseAgent",
    "ZhipuAgent",
    "build_zhipu_agent",
    "ZhipuFCallAgent",
    "build_zhipu_fcall_agent",
    "OpenAIAgent",
    "build_openai_agent",
    "OllamaAgent",
    "build_ollama_agent",

    # Factory Pattern
    "AgentFactory",
    "agent_factory",
    "BaseAgentFactory",
    "ZhipuAgentFactory",
    "OpenAIAgentFactory",
    "OllamaAgentFactory",
    "FactoryRegistry",
    "get_global_registry",

    # Builder Pattern
    "AgentBuilder",
    "AgentPresets",
] 