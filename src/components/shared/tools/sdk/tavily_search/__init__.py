"""
Tavily Search SDK Module

Provides comprehensive Tavily API integration for LangChain:
- Search: Web search with filtering
- Extract: URL content extraction
- Map: Website structure mapping
- Crawl: Website content crawling

All tools support both sync and async operations.
"""

from .config import (
    TavilyConfig,
    TavilyAPIConfig,
    TavilySearchConfig,
    TavilyExtractConfig,
    TavilyMapConfig,
    TavilyCrawlConfig,
    TavilyRateLimitConfig,
    TavilyCacheConfig,
    get_config,
    set_config,
    reset_config,
    get_config_summary,
    load_config_from_json,
    load_config_from_env
)

from .error_handler import (
    TavilyErrorType,
    TavilyErrorResponse,
    TavilyErrorHandler,
    RetryStrategy,
    with_tavily_error_handling,
    create_success_response,
    is_error_response
)

from .tavily_search_tool import (
    # Search tools
    tavily_search_basic,
    tavily_search_advanced,
    tavily_search_news,
    # Extract tools
    tavily_extract_url,
    tavily_extract_batch,
    # Map tools
    tavily_map_website,
    tavily_map_with_filter,
    # Crawl tools
    tavily_crawl_basic,
    tavily_crawl_targeted,
    # Tool lists
    TAVILY_SEARCH_TOOLS,
    TAVILY_EXTRACT_TOOLS,
    TAVILY_MAP_TOOLS,
    TAVILY_CRAWL_TOOLS,
    TAVILY_TOOLS,
    # Helper functions
    get_available_tavily_tools,
    get_tavily_search_tools,
    get_tavily_extract_tools,
    get_tavily_map_tools,
    get_tavily_crawl_tools
)

__all__ = [
    # Config classes
    "TavilyConfig",
    "TavilyAPIConfig",
    "TavilySearchConfig",
    "TavilyExtractConfig",
    "TavilyMapConfig",
    "TavilyCrawlConfig",
    "TavilyRateLimitConfig",
    "TavilyCacheConfig",
    # Config functions
    "get_config",
    "set_config",
    "reset_config",
    "get_config_summary",
    "load_config_from_json",
    "load_config_from_env",
    # Error handling
    "TavilyErrorType",
    "TavilyErrorResponse",
    "TavilyErrorHandler",
    "RetryStrategy",
    "with_tavily_error_handling",
    "create_success_response",
    "is_error_response",
    # Search tools
    "tavily_search_basic",
    "tavily_search_advanced",
    "tavily_search_news",
    # Extract tools
    "tavily_extract_url",
    "tavily_extract_batch",
    # Map tools
    "tavily_map_website",
    "tavily_map_with_filter",
    # Crawl tools
    "tavily_crawl_basic",
    "tavily_crawl_targeted",
    # Tool lists
    "TAVILY_SEARCH_TOOLS",
    "TAVILY_EXTRACT_TOOLS",
    "TAVILY_MAP_TOOLS",
    "TAVILY_CRAWL_TOOLS",
    "TAVILY_TOOLS",
    # Helper functions
    "get_available_tavily_tools",
    "get_tavily_search_tools",
    "get_tavily_extract_tools",
    "get_tavily_map_tools",
    "get_tavily_crawl_tools"
]
