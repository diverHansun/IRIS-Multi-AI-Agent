"""SubAgent middleware module for task delegation.

This module provides the core infrastructure for delegating tasks to specialized
subagents within the DeepAgents framework.

Architecture:
    - types.py: Data structures (SubAgent, CompiledSubAgent)
    - middleware.py: Middleware implementation (SubAgentMiddleware)

Usage:
    from src.components.deepagents.runtime_middlewares.subagents import (
        SubAgent,
        SubAgentMiddleware,
    )

Following SOLID principles:
    - SRP: Each submodule has a single, clear responsibility
    - OCP: New subagent types can be added via configuration
    - DIP: Middleware depends on abstractions, not concrete implementations
"""

from .types import SubAgent, CompiledSubAgent
from .middleware import SubAgentMiddleware

__all__ = [
    "SubAgent",
    "CompiledSubAgent",
    "SubAgentMiddleware",
]
