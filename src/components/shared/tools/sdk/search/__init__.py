"""
Search Tools Module

Manages various search tools including general web search utilities.
Note: Tavily search tools have been moved to src.components.shared.tools.sdk.tavily_search
"""

# Safe import of search tools, handle potential import errors
try:
    from .search_tools import get_available_search_tools, web_search_tool, web_search_detailed, get_webpage_content
except ImportError as e:
    print(f"Warning: Unable to import general search tools: {e}")
    get_available_search_tools = lambda: []
    web_search_tool = None
    web_search_detailed = None
    get_webpage_content = None

# Export all search tools
__all__ = [
    # General search tools
    'get_available_search_tools',
    'web_search_tool',
    'web_search_detailed',
    'get_webpage_content',
]

