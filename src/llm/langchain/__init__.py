"""
语言模型模块

提供各种LLM提供商的封装和管理。

架构说明：
- instances/: LLM具体实现（ZhipuAILLM, OpenAILLM, OllamaLLM）
- adapters/: 适配器模式（LLMAdapter, ZhipuAdapter, OpenAIAdapter, OllamaAdapter）
- managers/: LLM管理器
- utils/: 工具函数集合
"""

# LLM Instances
from .instances import (
    ZhipuAILLM,
    OpenAILLM,
    OllamaLLM,
)

# Adapter Pattern
from .adapters import (
    LLMAdapter,
    ZhipuAdapter,
    OpenAIAdapter,
    OllamaAdapter,
)

# LLM Manager
from .managers import (
    LLMManager,
    LLMProvider,
    get_llm_info,
)

# Utilities
from .utils import (
    # Ollama
    list_ollama_models,
    OllamaHttpClient,
    # Streaming
    StreamingLLM,
    stream_llm_response,
)

__all__ = [
    # Instances
    "ZhipuAILLM",
    "OpenAILLM",
    "OllamaLLM",

    # Adapters
    "LLMAdapter",
    "ZhipuAdapter",
    "OpenAIAdapter",
    "OllamaAdapter",

    # Managers
    "LLMManager",
    "LLMProvider",
    "get_llm_info",

    # Utils
    "list_ollama_models",
    "OllamaHttpClient",
    "StreamingLLM",
    "stream_llm_response",
] 