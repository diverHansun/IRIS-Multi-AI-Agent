"""
语言模型模块

提供各种LLM提供商的封装和管理。

架构说明：
- instances/: LLM具体实现（ZhipuLLM, OpenAILLM, OllamaLLM）
- adapters/: 适配器模式（LLMAdapter, ZhipuAdapter, OpenAIAdapter, OllamaAdapter）
- llm_manager.py: LLM管理器
"""

# LLM Instances
from .instances import (
    ZhipuLLM,
    OpenAILLM,
    OllamaLLM,
)

# Adapter Pattern (NEW)
from .adapters import (
    LLMAdapter,
    ZhipuAdapter,
    OpenAIAdapter,
    OllamaAdapter,
)

# LLM Manager
from .llm_manager import (
    LLMManager,
    LLMProvider,
    get_llm_info,
)

__all__ = [
    # LLM Instances
    "ZhipuLLM",
    "OpenAILLM",
    "OllamaLLM",

    # Adapter Pattern (NEW)
    "LLMAdapter",
    "ZhipuAdapter",
    "OpenAIAdapter",
    "OllamaAdapter",

    # LLM Manager
    "LLMManager",
    "LLMProvider",
    "get_llm_info",
] 