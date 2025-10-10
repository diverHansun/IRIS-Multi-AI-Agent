"""
Agent实例模块

提供各种Agent提供商的具体实现。
"""

from .base_agent import BaseAgent
from .zhipu_agent import ZhipuAgent, build_zhipu_agent
from .zhipu_fcall_agent import ZhipuFCallAgent, build_zhipu_fcall_agent
from .openai_agent import OpenAIAgent, build_openai_agent
from .ollama_agent import OllamaAgent, build_ollama_agent

__all__ = [
    "BaseAgent",
    "ZhipuAgent",
    "build_zhipu_agent",
    "ZhipuFCallAgent",
    "build_zhipu_fcall_agent",
    "OpenAIAgent",
    "build_openai_agent",
    "OllamaAgent",
    "build_ollama_agent",
]
