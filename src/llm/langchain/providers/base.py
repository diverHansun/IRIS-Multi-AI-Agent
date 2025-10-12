"""
Base Provider (Compatibility Layer)

This module has been moved to src.core.langchain.providers.
This compatibility layer will be removed in v5.0.

Please update your imports to:
    from src.core.langchain.providers import BaseProvider
"""

import warnings

warnings.warn(
    "BaseProvider has been moved to src.core.langchain.providers. "
    "Please update your imports. This compatibility layer will be removed in v5.0.",
    DeprecationWarning,
    stacklevel=2
)

from src.core.langchain.providers import BaseProvider

__all__ = ['BaseProvider']
