"""
Ollama Provider Utilities

Ollama-specific HTTP client and model discovery utilities.
"""

from .client import OllamaClient
from .utils import (
    get_ollama_models_http,
    get_ollama_models_cli,
    list_ollama_models,
    get_model_display_info,
    discover_models,
    is_ollama_available,
)

__all__ = [
    # HTTP Client
    "OllamaClient",

    # Model Discovery
    "get_ollama_models_http",
    "get_ollama_models_cli",
    "list_ollama_models",
    "get_model_display_info",
    "discover_models",
    "is_ollama_available",
]
