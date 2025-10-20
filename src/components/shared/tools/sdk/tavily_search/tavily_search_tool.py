"""
Tavily Search Tool Module

Provides LangChain tool wrappers for all Tavily API operations:
- TavilySearch: Web search with various filters
- TavilyExtract: Extract content from URLs
- TavilyMap: Map website structure
- TavilyCrawl: Crawl websites for content
"""

import logging
from typing import Annotated, Dict, List, Any, Optional, Literal
from langchain_core.tools import tool
from langchain_tavily import TavilySearch, TavilyExtract, TavilyMap, TavilyCrawl

from .config import get_config

logger = logging.getLogger(__name__)


# ============================================================================
# TavilySearch Tools - Web Search Operations
# ============================================================================


@tool
def tavily_search_basic(
    query: Annotated[str, "Search query to look up"]
) -> Dict[str, Any]:
    """
    Perform basic web search using Tavily Search API.

    This is a simple search tool optimized for quick, straightforward queries.
    Returns up to 5 results with basic search depth.

    Args:
        query: Search query string

    Returns:
        Dictionary containing search results with query, results list, and response_time
    """
    try:
        config = get_config()

        if not config.is_available():
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
            }

        logger.info(f"Executing Tavily basic search: {query}")

        search_tool = TavilySearch(
            tavily_api_key=config.api_key,
            max_results=config.search.max_results,
            search_depth=config.search.search_depth,
            topic=config.search.topic,
            include_answer=config.search.include_answer,
            include_raw_content=config.search.include_raw_content
        )

        results = search_tool.invoke({"query": query})
        return results

    except Exception as e:
        logger.error(f"Tavily basic search failed: {e}")
        return {"error": f"Search failed: {str(e)}"}


@tool
def tavily_search_advanced(
    query: Annotated[str, "Search query to look up"],
    max_results: Annotated[int, "Maximum number of results (1-20)"] = 10,
    search_depth: Annotated[Literal["basic", "advanced"], "Search depth level"] = "advanced",
    topic: Annotated[Literal["general", "news", "finance"], "Search category"] = "general",
    include_answer: Annotated[bool, "Include AI-generated answer summary"] = True,
    include_raw_content: Annotated[bool, "Include full page content in markdown"] = False,
    include_images: Annotated[bool, "Include related images"] = False,
    time_range: Annotated[Optional[Literal["day", "week", "month", "year"]], "Filter by time range"] = None,
    include_domains: Annotated[Optional[List[str]], "Only search these domains"] = None,
    exclude_domains: Annotated[Optional[List[str]], "Exclude these domains"] = None
) -> Dict[str, Any]:
    """
    Perform advanced web search with comprehensive filtering options.

    Supports advanced search depth, domain filtering, time range filtering,
    and various content inclusion options for detailed research.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (1-20)
        search_depth: Search thoroughness - "basic" for quick results, "advanced" for comprehensive
        topic: Search category - "general", "news", or "finance"
        include_answer: Whether to include AI-generated answer summary
        include_raw_content: Whether to include full page content in markdown format
        include_images: Whether to include related images in results
        time_range: Filter results by recency - "day", "week", "month", or "year"
        include_domains: List of domains to restrict search to (e.g., ["wikipedia.org"])
        exclude_domains: List of domains to exclude from search

    Returns:
        Dictionary containing search results with query, results list, optional answer, and response_time
    """
    try:
        config = get_config()

        if not config.is_available():
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
            }

        # Validate and constrain parameters
        max_results = max(1, min(20, max_results))

        logger.info(f"Executing Tavily advanced search: {query} (depth={search_depth}, results={max_results})")

        search_tool = TavilySearch(
            tavily_api_key=config.api_key,
            max_results=max_results,
            search_depth=search_depth,
            topic=topic,
            include_answer=include_answer,
            include_raw_content="markdown" if include_raw_content else False,
            include_images=include_images,
            time_range=time_range,
            include_domains=include_domains or [],
            exclude_domains=exclude_domains or []
        )

        results = search_tool.invoke({"query": query})
        return results

    except Exception as e:
        logger.error(f"Tavily advanced search failed: {e}")
        return {"error": f"Advanced search failed: {str(e)}"}


@tool
def tavily_search_news(
    query: Annotated[str, "News search query"],
    max_results: Annotated[int, "Maximum number of news results"] = 8,
    time_range: Annotated[Literal["day", "week", "month"], "News recency filter"] = "week"
) -> Dict[str, Any]:
    """
    Search for recent news articles using Tavily.

    Optimized for news content with topic set to "news" and recent time filtering.
    Returns results from major news sources and publications.

    Args:
        query: News search query
        max_results: Maximum number of news results (1-20)
        time_range: How recent the news should be - "day", "week", or "month"

    Returns:
        Dictionary containing news search results
    """
    try:
        config = get_config()

        if not config.is_available():
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
            }

        max_results = max(1, min(20, max_results))

        logger.info(f"Executing Tavily news search: {query} (time_range={time_range})")

        search_tool = TavilySearch(
            tavily_api_key=config.api_key,
            max_results=max_results,
            search_depth="advanced",
            topic="news",
            include_answer=True,
            time_range=time_range,
            include_raw_content=False
        )

        results = search_tool.invoke({"query": query})
        return results

    except Exception as e:
        logger.error(f"Tavily news search failed: {e}")
        return {"error": f"News search failed: {str(e)}"}


# ============================================================================
# TavilyExtract Tools - URL Content Extraction
# ============================================================================


@tool
def tavily_extract_url(
    url: Annotated[str, "URL to extract content from"],
    extract_depth: Annotated[Literal["basic", "advanced"], "Extraction depth"] = "basic",
    include_images: Annotated[bool, "Include images from the page"] = False,
    format: Annotated[Literal["markdown", "text"], "Content format"] = "markdown"
) -> Dict[str, Any]:
    """
    Extract clean content from a single URL using Tavily Extract API.

    Retrieves parsed and cleaned content from web pages, removing ads,
    navigation, and other non-content elements.

    Args:
        url: URL to extract content from
        extract_depth: Extraction thoroughness - "basic" or "advanced"
        include_images: Whether to include images from the page
        format: Output format - "markdown" or "text"

    Returns:
        Dictionary with extracted content including url, raw_content, and images
    """
    try:
        config = get_config()

        if not config.is_available():
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
            }

        logger.info(f"Extracting content from URL: {url}")

        extract_tool = TavilyExtract(
            tavily_api_key=config.api_key,
            extract_depth=extract_depth,
            include_images=include_images,
            format=format
        )

        result = extract_tool.invoke({"urls": [url]})
        return result

    except Exception as e:
        logger.error(f"Tavily URL extraction failed: {e}")
        return {"error": f"URL extraction failed: {str(e)}"}


@tool
def tavily_extract_batch(
    urls: Annotated[List[str], "List of URLs to extract content from"],
    extract_depth: Annotated[Literal["basic", "advanced"], "Extraction depth"] = "basic",
    format: Annotated[Literal["markdown", "text"], "Content format"] = "markdown"
) -> Dict[str, Any]:
    """
    Extract clean content from multiple URLs in batch using Tavily Extract API.

    Efficiently extracts content from multiple pages in a single request.
    Useful for processing multiple articles or pages at once.

    Args:
        urls: List of URLs to extract content from
        extract_depth: Extraction thoroughness - "basic" or "advanced"
        format: Output format - "markdown" or "text"

    Returns:
        Dictionary with results list containing extracted content and failed_results
    """
    try:
        config = get_config()

        if not config.is_available():
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
            }

        if not urls or len(urls) == 0:
            return {"error": "No URLs provided for extraction"}

        logger.info(f"Batch extracting content from {len(urls)} URLs")

        extract_tool = TavilyExtract(
            tavily_api_key=config.api_key,
            extract_depth=extract_depth,
            include_images=False,
            format=format
        )

        result = extract_tool.invoke({"urls": urls})
        return result

    except Exception as e:
        logger.error(f"Tavily batch extraction failed: {e}")
        return {"error": f"Batch extraction failed: {str(e)}"}


# ============================================================================
# TavilyMap Tools - Website Structure Mapping
# ============================================================================


@tool
def tavily_map_website(
    url: Annotated[str, "Base URL to map"],
    max_depth: Annotated[int, "Maximum depth to crawl from base URL"] = 1,
    max_breadth: Annotated[int, "Maximum links to follow per page"] = 20,
    limit: Annotated[int, "Total number of URLs to process"] = 50
) -> Dict[str, Any]:
    """
    Map the structure of a website by discovering and organizing its URLs.

    Creates a structured map of a website's URLs without extracting content.
    Useful for understanding site architecture and discovering pages.

    Args:
        url: Base URL to start mapping from
        max_depth: How many levels deep to crawl from the base URL
        max_breadth: Maximum number of links to follow on each page
        limit: Total number of URLs to process before stopping

    Returns:
        Dictionary with base_url, results (list of discovered URLs), and response_time
    """
    try:
        config = get_config()

        if not config.is_available():
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
            }

        logger.info(f"Mapping website structure: {url}")

        map_tool = TavilyMap(
            tavily_api_key=config.api_key,
            max_depth=max_depth,
            max_breadth=max_breadth,
            limit=limit,
            allow_external=False
        )

        result = map_tool.invoke({"url": url})
        return result

    except Exception as e:
        logger.error(f"Tavily website mapping failed: {e}")
        return {"error": f"Website mapping failed: {str(e)}"}


@tool
def tavily_map_with_filter(
    url: Annotated[str, "Base URL to map"],
    instructions: Annotated[Optional[str], "Natural language instructions for filtering"] = None,
    categories: Annotated[Optional[List[str]], "Filter by categories"] = None,
    select_paths: Annotated[Optional[List[str]], "Regex patterns to include paths"] = None,
    exclude_paths: Annotated[Optional[List[str]], "Regex patterns to exclude paths"] = None,
    max_depth: Annotated[int, "Maximum crawl depth"] = 2,
    limit: Annotated[int, "Total URL limit"] = 50
) -> Dict[str, Any]:
    """
    Map website structure with advanced filtering options.

    Allows filtering URLs by natural language instructions, categories,
    or regex path patterns for targeted site mapping.

    Args:
        url: Base URL to start mapping from
        instructions: Natural language instructions to guide URL selection
        categories: Filter by predefined categories (e.g., ["Documentation", "Blogs"])
        select_paths: Regex patterns to include specific URL paths
        exclude_paths: Regex patterns to exclude specific URL paths
        max_depth: How many levels deep to crawl
        limit: Total number of URLs to process

    Returns:
        Dictionary with base_url, filtered results, and response_time
    """
    try:
        config = get_config()

        if not config.is_available():
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
            }

        logger.info(f"Mapping website with filters: {url}")

        map_tool = TavilyMap(
            tavily_api_key=config.api_key,
            max_depth=max_depth,
            max_breadth=20,
            limit=limit,
            instructions=instructions,
            categories=categories,
            select_paths=select_paths or [],
            exclude_paths=exclude_paths or [],
            allow_external=False
        )

        result = map_tool.invoke({"url": url})
        return result

    except Exception as e:
        logger.error(f"Tavily filtered mapping failed: {e}")
        return {"error": f"Filtered mapping failed: {str(e)}"}


# ============================================================================
# TavilyCrawl Tools - Website Content Crawling
# ============================================================================


@tool
def tavily_crawl_basic(
    url: Annotated[str, "Base URL to crawl"],
    max_depth: Annotated[int, "Maximum crawl depth from base URL"] = 1,
    max_breadth: Annotated[int, "Maximum links per page"] = 20,
    limit: Annotated[int, "Total pages to crawl"] = 50
) -> Dict[str, Any]:
    """
    Crawl a website and extract content from discovered pages.

    Combines website mapping with content extraction. Discovers pages
    and extracts their content in a single operation.

    Args:
        url: Base URL to start crawling from
        max_depth: How many levels deep to crawl from base URL
        max_breadth: Maximum number of links to follow on each page
        limit: Total number of pages to crawl and extract

    Returns:
        Dictionary with base_url, results (list of pages with extracted content), and response_time
    """
    try:
        config = get_config()

        if not config.is_available():
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
            }

        logger.info(f"Crawling website: {url}")

        crawl_tool = TavilyCrawl(
            tavily_api_key=config.api_key,
            max_depth=max_depth,
            max_breadth=max_breadth,
            limit=limit,
            allow_external=False,
            extract_depth=config.crawl.extract_depth,
            format=config.crawl.format
        )

        result = crawl_tool.invoke({"url": url})
        return result

    except Exception as e:
        logger.error(f"Tavily website crawl failed: {e}")
        return {"error": f"Website crawl failed: {str(e)}"}


@tool
def tavily_crawl_targeted(
    url: Annotated[str, "Base URL to crawl"],
    instructions: Annotated[str, "Natural language instructions for targeted crawling"],
    categories: Annotated[Optional[List[str]], "Filter pages by categories"] = None,
    max_depth: Annotated[int, "Maximum crawl depth"] = 2,
    limit: Annotated[int, "Total pages to crawl"] = 50,
    include_images: Annotated[bool, "Include images from crawled pages"] = False
) -> Dict[str, Any]:
    """
    Crawl a website with targeted filtering using natural language instructions.

    Allows precise control over which pages to crawl and extract using
    natural language instructions and category filtering.

    Args:
        url: Base URL to start crawling from
        instructions: Natural language instructions to guide crawling (e.g., "Find all blog posts")
        categories: Filter by predefined categories (e.g., ["Documentation", "Careers"])
        max_depth: How many levels deep to crawl
        limit: Total number of pages to crawl
        include_images: Whether to include images from crawled pages

    Returns:
        Dictionary with base_url, filtered and extracted results, and response_time
    """
    try:
        config = get_config()

        if not config.is_available():
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY environment variable."
            }

        logger.info(f"Targeted crawling website: {url} with instructions: {instructions}")

        crawl_tool = TavilyCrawl(
            tavily_api_key=config.api_key,
            max_depth=max_depth,
            max_breadth=20,
            limit=limit,
            instructions=instructions,
            categories=categories,
            allow_external=False,
            include_images=include_images,
            extract_depth="advanced",
            format="markdown"
        )

        result = crawl_tool.invoke({"url": url})
        return result

    except Exception as e:
        logger.error(f"Tavily targeted crawl failed: {e}")
        return {"error": f"Targeted crawl failed: {str(e)}"}


# ============================================================================
# Tool Lists and Exports
# ============================================================================

# Search tools
TAVILY_SEARCH_TOOLS = [
    tavily_search_basic,
    tavily_search_advanced,
    tavily_search_news
]

# Extract tools
TAVILY_EXTRACT_TOOLS = [
    tavily_extract_url,
    tavily_extract_batch
]

# Map tools
TAVILY_MAP_TOOLS = [
    tavily_map_website,
    tavily_map_with_filter
]

# Crawl tools
TAVILY_CRAWL_TOOLS = [
    tavily_crawl_basic,
    tavily_crawl_targeted
]

# All Tavily tools combined
TAVILY_TOOLS = (
    TAVILY_SEARCH_TOOLS +
    TAVILY_EXTRACT_TOOLS +
    TAVILY_MAP_TOOLS +
    TAVILY_CRAWL_TOOLS
)


def get_available_tavily_tools() -> List[Any]:
    """
    Get list of available Tavily tools.

    Returns empty list if Tavily API key is not configured.

    Returns:
        List of Tavily tool functions
    """
    config = get_config()

    if not config.is_available():
        logger.warning("Tavily API key not configured, returning empty tool list")
        return []

    return TAVILY_TOOLS


def get_tavily_search_tools() -> List[Any]:
    """Get only search-related Tavily tools"""
    config = get_config()
    return TAVILY_SEARCH_TOOLS if config.is_available() else []


def get_tavily_extract_tools() -> List[Any]:
    """Get only extraction-related Tavily tools"""
    config = get_config()
    return TAVILY_EXTRACT_TOOLS if config.is_available() else []


def get_tavily_map_tools() -> List[Any]:
    """Get only mapping-related Tavily tools"""
    config = get_config()
    return TAVILY_MAP_TOOLS if config.is_available() else []


def get_tavily_crawl_tools() -> List[Any]:
    """Get only crawling-related Tavily tools"""
    config = get_config()
    return TAVILY_CRAWL_TOOLS if config.is_available() else []
