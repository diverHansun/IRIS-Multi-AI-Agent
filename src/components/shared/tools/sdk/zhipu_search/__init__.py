"""
Zhipu Web Search Tools Package

Provides web search functionality using Zhipu AI's search API.
"""

from .config import (
    ZhipuConfig,
    ZhipuAPIConfig,
    ZhipuSearchConfig,
    ZhipuCacheConfig,
    ZhipuCrawlConfig,
    ZhipuCrawlAPIConfig,
    ZhipuCrawlRequestConfig,
    ZhipuCrawlCacheConfig,
    get_config,
    get_crawl_config,
    set_config,
    set_crawl_config,
    reset_config,
    reset_crawl_config,
    get_config_summary,
    get_crawl_config_summary
)

from .zhipu_search_tools import (
    zhipu_web_search,
    get_available_zhipu_tools,
    ZHIPU_SEARCH_TOOLS
)
from .zhipu_crawl_tools import (
    zhipu_web_crawl,
    ZHIPU_CRAWL_TOOLS
)

__all__ = [
    # Configuration
    "ZhipuConfig",
    "ZhipuAPIConfig",
    "ZhipuSearchConfig",
    "ZhipuCacheConfig",
    "ZhipuCrawlConfig",
    "ZhipuCrawlAPIConfig",
    "ZhipuCrawlRequestConfig",
    "ZhipuCrawlCacheConfig",
    "get_config",
    "get_crawl_config",
    "set_config",
    "set_crawl_config",
    "reset_config",
    "reset_crawl_config",
    "get_config_summary",
    "get_crawl_config_summary",

    # Tools
    "zhipu_web_search",
    "get_available_zhipu_tools",
    "ZHIPU_SEARCH_TOOLS",
    "zhipu_web_crawl",
    "ZHIPU_CRAWL_TOOLS"
]
