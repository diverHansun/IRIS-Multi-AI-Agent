"""
Provider-specific utilities and clients

This module contains provider-specific tools and implementations.
Each provider has its own subdirectory with dedicated utilities.

Structure:
- ollama/: Ollama-specific HTTP client and utilities
- zhipu/: Zhipu AI-specific utilities (reserved)
- openai/: OpenAI-specific utilities (reserved)
"""

# Ollama provider
from .ollama import (
    OllamaClient,
    list_ollama_models,
    get_ollama_models_http,
    get_ollama_models_cli,
)

__all__ = [
    # Ollama
    "OllamaClient",
    "list_ollama_models",
    "get_ollama_models_http",
    "get_ollama_models_cli",
]
