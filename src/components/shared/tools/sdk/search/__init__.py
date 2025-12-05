"""
Search Tools Module

Provides DuckDuckGo Instant Answer search and legacy search utilities.
"""

import logging

logger = logging.getLogger(__name__)

# DuckDuckGo Instant Answer (Free API)
try:
    from .duckduckgo_search_tools import duckduckgo_instant_answer, get_available_tools as get_duckduckgo_tools
except ImportError as e:
    logger.debug(f"Unable to import DuckDuckGo search tools: {e}")
    duckduckgo_instant_answer = None
    get_duckduckgo_tools = lambda: []

# Legacy search tools (for backward compatibility)
try:
    from .search_tools import get_available_search_tools, web_search_basic, get_webpage_content
except ImportError as e:
    logger.debug(f"Unable to import legacy search tools: {e}")
    get_available_search_tools = lambda: []
    web_search_basic = None
    get_webpage_content = None


def get_all_search_tools():
    """
    Get all available search tools including DuckDuckGo Instant Answer and legacy HTML scraping tools.

    Returns:
        List of all search tool functions
    """
    tools = []
    # Add DuckDuckGo Instant Answer API tools
    tools.extend(get_duckduckgo_tools())
    # Add legacy HTML scraping search tools
    tools.extend(get_available_search_tools())
    return tools


# Export all search tools
__all__ = [
    # DuckDuckGo Search
    'duckduckgo_instant_answer',
    'get_duckduckgo_tools',

    # Unified
    'get_all_search_tools',

    # Legacy (for backward compatibility)
    'get_available_search_tools',
    'web_search_basic',
    'get_webpage_content',
]

