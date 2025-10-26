"""
智能代理模块

提供各种Agent提供商的实现。

架构说明：
- instances/: Agent具体实现（BaseAgent, ZhipuAgent, OpenAIAgent）
- factories/: 抽象工厂模式（FactoryRegistry, ZhipuFactory, OpenAIFactory）
- builders/: 建造者模式（AgentBuilder, AgentPresets）
- agent_factory.py: 统一工厂入口（内部使用Registry，保持向后兼容）
"""

# Agent Instances
from .instances import (
    BaseAgent,
    ZhipuAgent,
    ZhipuFCallAgent,
    OpenAIAgent,
)

# Factory Pattern - 现在从 factories 模块导入
from .factories import (
    # Abstract Factory Pattern
    BaseAgentFactory,
    ZhipuAgentFactory,
    OpenAIAgentFactory,
    FactoryRegistry,
    get_global_registry,
    agent_factory,
)

# 向后兼容：AgentFactory 类别名
AgentFactory = FactoryRegistry

# Builder Pattern removed in v4.0
# Use agent_manager.create_agent() instead

# Manager Pattern (Recommended)
from .managers import (
    agent_manager,
    AgentManager,
)

__all__ = [
    # Recommended API
    "agent_manager",
    "AgentManager",

    # Agent instances
    "BaseAgent",
    "ZhipuAgent",
    "ZhipuFCallAgent",
    "OpenAIAgent",

    # Factory Pattern
    "AgentFactory",
    "agent_factory",
    "BaseAgentFactory",
    "ZhipuAgentFactory",
    "OpenAIAgentFactory",
    "FactoryRegistry",
    "get_global_registry",
] 