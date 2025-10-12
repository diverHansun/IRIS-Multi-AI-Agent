"""
Provider Registry (Compatibility Layer)

This module has been moved to src.core.langchain.providers.
This compatibility layer will be removed in v5.0.

Please update your imports to:
    from src.core.langchain.providers import provider_registry, ProviderRegistry
"""

import warnings

warnings.warn(
    "ProviderRegistry has been moved to src.core.langchain.providers. "
    "Please update your imports. This compatibility layer will be removed in v5.0.",
    DeprecationWarning,
    stacklevel=2
)

from src.core.langchain.providers import (
    ProviderRegistry,
    provider_registry,
    LLMProvider
)

__all__ = ['ProviderRegistry', 'provider_registry', 'LLMProvider']
