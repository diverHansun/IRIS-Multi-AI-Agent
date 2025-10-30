"""
Zhipu Web Search Tools Package

Provides web search functionality using Zhipu AI's search API.
"""

from .config import (
    ZhipuConfig,
    ZhipuAPIConfig,
    ZhipuSearchConfig,
    ZhipuCacheConfig,
    get_config,
    set_config,
    reset_config,
    get_config_summary
)

from .zhipu_search_tools import (
    zhipu_web_search,
    get_available_zhipu_tools,
    ZHIPU_SEARCH_TOOLS
)

__all__ = [
    # Configuration
    "ZhipuConfig",
    "ZhipuAPIConfig",
    "ZhipuSearchConfig",
    "ZhipuCacheConfig",
    "get_config",
    "set_config",
    "reset_config",
    "get_config_summary",

    # Tools
    "zhipu_web_search",
    "get_available_zhipu_tools",
    "ZHIPU_SEARCH_TOOLS"
]
