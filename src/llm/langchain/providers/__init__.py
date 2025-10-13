"""
Provider-specific utilities and clients

This module contains provider-specific tools and implementations.
Each provider has its own subdirectory with dedicated utilities.

Structure:
- BaseProvider: abstract base class (from core module)
- zhipu/: 智谱AI Provider实现和工具
  - provider.py: ZhipuProvider implementation
- openai/: OpenAI Provider实现和工具
  - provider.py: OpenAIProvider implementation
- ollama/: Ollama Provider实现、HTTP客户端和工具
  - provider.py: OllamaProvider implementation
  - client.py: HTTP client
  - utils.py: Model discovery utilities
"""

# Base Provider (imported from core module)
from src.core.langchain.providers import BaseProvider

# Provider implementations (从子目录导入)
from .zhipu import ZhipuProvider
from .openai import OpenAIProvider
from .ollama import OllamaProvider

# Ollama utilities (for compatibility)
from .ollama import (
    OllamaClient,
    list_ollama_models,
    get_ollama_models_http,
    get_ollama_models_cli,
)

__all__ = [
    # Base & Provider implementations
    "BaseProvider",
    "ZhipuProvider",
    "OpenAIProvider",
    "OllamaProvider",
    # Ollama utilities
    "OllamaClient",
    "list_ollama_models",
    "get_ollama_models_http",
    "get_ollama_models_cli",
]
