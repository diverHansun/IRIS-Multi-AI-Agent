"""
BasicAgents Module - Refactored Architecture

Streamlined agent creation with Adapter pattern (Factory layer removed).

Architecture:
- instances/: Agent implementations (BaseAgent, ZhipuAgent, OpenAIAgent)
- adapters/: Provider-specific adapters for LLM/graph creation
- managers/: Agent manager for unified agent creation
- config.py: Centralized configuration via AgentConfig
- exceptions.py: Unified error handling

Usage:
    from src.agents.basicagents import agent_manager

    agent = await agent_manager.create_agent("zhipu", "glm-4.7-flash")
    result = await agent.invoke("query", session_id="user123")
"""

# Agent Instances
from .instances import (
    BaseAgent,
    ZhipuAgent,
    ZhipuFCallAgent,
    OpenAIAgent,
)

# Manager Pattern (Recommended API)
from .managers import (
    agent_manager,
    AgentManager,
    create_agent,
    get_available_agents,
)

# Configuration
from .config import AgentConfig

# Exceptions
from .exceptions import (
    BasicAgentError,
    ConfigurationError,
    AuthenticationError,
    ProviderNotFoundError,
    ModelNotFoundError,
    AgentCreationError,
)

__all__ = [
    # Recommended API
    "agent_manager",
    "AgentManager",
    "create_agent",
    "get_available_agents",

    # Agent instances
    "BaseAgent",
    "ZhipuAgent",
    "ZhipuFCallAgent",
    "OpenAIAgent",

    # Configuration
    "AgentConfig",

    # Exceptions
    "BasicAgentError",
    "ConfigurationError",
    "AuthenticationError",
    "ProviderNotFoundError",
    "ModelNotFoundError",
    "AgentCreationError",
] 