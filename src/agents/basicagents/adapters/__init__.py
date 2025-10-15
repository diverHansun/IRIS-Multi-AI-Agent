"""
Agent Adapters Module

Agent参数适配器，处理Agent相关的配置参数。
只处理Agent参数，不处理LLM参数。
"""

from .base import AgentAdapter
from .zhipu_agent_adapter import ZhipuAgentAdapter
from .openai_agent_adapter import OpenAIAgentAdapter
from .ollama_agent_adapter import OllamaAgentAdapter

__all__ = [
    "AgentAdapter",
    "ZhipuAgentAdapter",
    "OpenAIAgentAdapter",
    "OllamaAgentAdapter",
]
