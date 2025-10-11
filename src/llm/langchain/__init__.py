"""
Language Model Module

Provides LLM provider wrappers and management.

Architecture:
- instances/: LLM implementations (ZhipuAILLM, OpenAILLM, OllamaLLM)
- adapters/: Adapter pattern (LLMAdapter, ZhipuAdapter, OpenAIAdapter, OllamaAdapter)
- managers/: LLM manager
- providers/: Provider-specific utilities (ollama, zhipu, openai)
- utils/: General utilities (streaming)
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

# Provider-specific utilities
from .providers.ollama import (
    OllamaClient,
    list_ollama_models,
)

# General utilities
from .utils import (
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

    # Provider utilities
    "OllamaClient",
    "list_ollama_models",

    # General utilities
    "StreamingLLM",
    "stream_llm_response",
] 