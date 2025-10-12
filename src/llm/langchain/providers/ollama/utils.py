"""
Ollama Utilities (Compatibility Layer)

This module has been moved to src.core.langchain.providers.utils.ollama.
This compatibility layer will be removed in v5.0.

Please update your imports to:
    from src.core.langchain.providers.utils import list_ollama_models
    from src.core.langchain.providers.utils.ollama import (
        get_ollama_models_http,
        get_ollama_models_cli,
        discover_models,
        is_ollama_available
    )
"""

import warnings

warnings.warn(
    "Ollama utilities have been moved to src.core.langchain.providers.utils.ollama. "
    "Please update your imports. This compatibility layer will be removed in v5.0.",
    DeprecationWarning,
    stacklevel=2
)

from src.core.langchain.providers.utils.ollama import (
    list_ollama_models,
    get_ollama_models_http,
    get_ollama_models_cli,
    discover_models,
    is_ollama_available,
    get_model_display_info
)

__all__ = [
    'list_ollama_models',
    'get_ollama_models_http',
    'get_ollama_models_cli',
    'discover_models',
    'is_ollama_available',
    'get_model_display_info',
]
