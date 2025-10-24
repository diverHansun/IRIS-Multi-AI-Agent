"""
Core Providers Module

Provides separated provider configuration management for LLM and BasicAgents modules.
"""

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
    'llm_registry',
    'basicagents_registry',

    # Classes (for advanced users)
    'LLMProviderRegistry',
    'BasicAgentsProviderRegistry',

    # Ollama utilities
    'list_ollama_models',
    'get_ollama_models_http',
    'get_ollama_models_cli',
    'discover_models',
    'is_ollama_available',
    'get_model_display_info',
]
