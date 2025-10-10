"""
LLM Adapters

适配器模式实现，用于统一处理不同LLM提供商的配置和参数。
"""

from .base import LLMAdapter
from .zhipu_adapter import ZhipuAdapter
from .openai_adapter import OpenAIAdapter
from .ollama_adapter import OllamaAdapter

__all__ = [
    "LLMAdapter",
    "ZhipuAdapter",
    "OpenAIAdapter",
    "OllamaAdapter",
]
