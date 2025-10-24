"""Manager layer for DeepAgents."""

from .subagent_manager import SubAgentManager
from .deep_agent_manager import DeepAgentManager

subagent_manager = SubAgentManager()
deep_agent_manager = DeepAgentManager(subagent_manager=subagent_manager)

__all__ = [
    "DeepAgentManager",
    "SubAgentManager",
    "deep_agent_manager",
    "subagent_manager",
]
