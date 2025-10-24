"""
Core Providers Module

Provides shared Provider abstractions and configuration management.
"""

from .provider_registry import ProviderRegistry, provider_registry, LLMProvider
from .llm_provider_registry import LLMProviderRegistry, llm_registry
from .basicagents_provider_registry import BasicAgentsProviderRegistry, basicagents_registry
from .utils.ollama import (
    list_ollama_models,
    get_ollama_models_http,
    get_ollama_models_cli,
    discover_models,
    is_ollama_available,
    get_model_display_info
)

__all__ = [
    # Recommended API (module-level instances)
    'provider_registry',
    'llm_registry',
    'basicagents_registry',

    # Classes (for advanced users)
    'ProviderRegistry',
    'LLMProviderRegistry',
    'BasicAgentsProviderRegistry',
    'LLMProvider',

    # Ollama utilities
    'list_ollama_models',
    'get_ollama_models_http',
    'get_ollama_models_cli',
    'discover_models',
    'is_ollama_available',
    'get_model_display_info',
]
