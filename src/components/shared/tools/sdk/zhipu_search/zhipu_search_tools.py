"""
Zhipu Web Search Tool Module

Provides LangChain tool wrapper for Zhipu Web Search API.
"""

import json
import logging
import time
import uuid
from typing import Annotated, Dict, List, Any, Optional, Tuple

import requests
from requests.exceptions import RequestException, HTTPError

from langchain_core.tools import tool

from .config import get_config

logger = logging.getLogger(__name__)


class SimpleCache:
    """Simple in-memory cache with expiration"""

    def __init__(self, expire_seconds: int):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._expire_seconds = expire_seconds

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._expire_seconds:
                logger.debug(f"Cache hit for key: {key}")
                return value
            else:
                del self._cache[key]
                logger.debug(f"Cache expired for key: {key}")
        return None

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = (value, time.time())
        logger.debug(f"Cache set for key: {key}")

    def clear(self) -> None:
        self._cache.clear()
        logger.debug("Cache cleared")


class ZhipuSearchProvider:
    """Zhipu Web Search API provider"""

    def __init__(self):
        """Initialize Zhipu Search provider"""
        self.config = get_config()
        self.session = requests.Session()

        # Initialize cache if enabled
        self.cache = None
        if self.config.cache.enable_cache:
            self.cache = SimpleCache(self.config.cache.cache_expire_seconds)
            logger.info(f"Cache enabled with {self.config.cache.cache_expire_seconds}s expiration")

    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        return f"zhipu_search_{uuid.uuid4().hex}"

    def _generate_user_id(self) -> str:
        """Generate user ID (6-128 characters as required by API)"""
        return f"user_{uuid.uuid4().hex[:16]}"

    def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to Zhipu Web Search API with retry logic

        Args:
            payload: Request payload

        Returns:
            Response data dictionary

        Raises:
            HTTPError: If request fails after retries
            RequestException: For other request errors
        """
        if not self.config.is_available():
            raise ValueError("Zhipu API key not configured. Please set ZHIPU_API_KEY environment variable.")

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        max_retries = self.config.api.max_retries
        retry_delay = self.config.api.retry_delay

        for attempt in range(max_retries + 1):
            try:
                response = self.session.post(
                    self.config.api.base_url,
                    json=payload,
                    headers=headers,
                    timeout=self.config.api.timeout
                )
                response.raise_for_status()
                return response.json()

            except HTTPError as e:
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {max_retries + 1} attempts: {e}")
                    raise

            except RequestException as e:
                logger.error(f"Request exception: {e}")
                raise

    def search(self, query: str) -> Dict[str, Any]:
        """
        Perform web search using Zhipu Search API

        Args:
            query: Search query string (max 70 characters)

        Returns:
            Dictionary containing search results
        """
        # Validate query length
        if len(query) > 70:
            logger.warning(f"Query length {len(query)} exceeds 70 characters, truncating")
            query = query[:70]

        # Check cache if enabled
        if self.cache:
            cache_key = f"search_{query}_{self.config.search.search_engine}"
            cached_result = self.cache.get(cache_key)
            if cached_result:
                logger.info(f"Returning cached result for query: {query}")
                return cached_result

        # Build request payload
        payload = {
            "search_query": query,
            "search_engine": self.config.search.search_engine,
            "search_intent": self.config.search.search_intent,
            "count": self.config.search.count,
            "search_recency_filter": self.config.search.search_recency_filter,
            "content_size": self.config.search.content_size,
            "request_id": self._generate_request_id(),
            "user_id": self._generate_user_id()
        }

        # Add domain filter if specified
        if self.config.search.search_domain_filter:
            payload["search_domain_filter"] = self.config.search.search_domain_filter

        try:
            logger.info(f"Executing Zhipu search: {query} (engine={self.config.search.search_engine})")
            result = self._make_request(payload)

            # Cache result if enabled
            if self.cache:
                self.cache.set(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"Zhipu search failed: {e}")
            return {"error": str(e)}


# Global search provider instance
_search_provider: Optional[ZhipuSearchProvider] = None


def get_search_provider() -> ZhipuSearchProvider:
    """Get global search provider instance (singleton pattern)"""
    global _search_provider
    if _search_provider is None:
        _search_provider = ZhipuSearchProvider()
    return _search_provider


def format_search_results(result: Dict[str, Any]) -> str:
    """
    Format search results as JSON string for LLM consumption

    Args:
        result: Raw API response

    Returns:
        Formatted JSON string with search results
    """
    if "error" in result:
        return json.dumps({
            "status": "error",
            "error": result["error"]
        }, ensure_ascii=False, indent=2)

    # Extract search results
    search_results = result.get("search_result", [])
    search_intent = result.get("search_intent", [])

    # Build formatted output
    output = {
        "status": "success",
        "id": result.get("id", ""),
        "request_id": result.get("request_id", ""),
        "created": result.get("created", 0),
        "total_results": len(search_results),
        "search_intent": search_intent,
        "results": []
    }

    # Format each search result
    for result_item in search_results:
        formatted_item = {
            "title": result_item.get("title", ""),
            "content": result_item.get("content", ""),
            "link": result_item.get("link", ""),
            "media": result_item.get("media", ""),
            "icon": result_item.get("icon", ""),
            "refer": result_item.get("refer", ""),
            "publish_date": result_item.get("publish_date", "")
        }
        output["results"].append(formatted_item)

    return json.dumps(output, ensure_ascii=False, indent=2)


@tool
def zhipu_web_search(
    query: Annotated[str, "Search query string, max 70 characters"]
) -> str:
    """
    Perform web search using Zhipu Web Search API.

    Uses Zhipu's AI-enhanced search engine optimized for large language models.
    Returns structured search results with title, content, link, media, icon,
    refer, and publish_date fields.

    Search configuration (engine, count, filters) is set in zhipu_search.json.

    Args:
        query: Search query string (max 70 characters)

    Returns:
        JSON string containing search results with all available fields

    Examples:
        zhipu_web_search("Python tutorial") -> Returns search results about Python
        zhipu_web_search("latest AI news") -> Returns recent AI-related articles
    """
    try:
        provider = get_search_provider()

        if not provider.config.is_available():
            return json.dumps({
                "status": "error",
                "error": "Zhipu API key not configured. Please set ZHIPU_API_KEY environment variable."
            }, ensure_ascii=False, indent=2)

        result = provider.search(query)
        return format_search_results(result)

    except Exception as e:
        logger.error(f"Zhipu web search tool execution failed: {e}")
        return json.dumps({
            "status": "error",
            "error": f"Search execution failed: {str(e)}"
        }, ensure_ascii=False, indent=2)


# Tool list for export
ZHIPU_SEARCH_TOOLS = [zhipu_web_search]


def get_available_zhipu_tools() -> List[Any]:
    """
    Get list of available Zhipu tools.

    Returns empty list if Zhipu API key is not configured.

    Returns:
        List of Zhipu tool functions
    """
    config = get_config()

    if not config.is_available():
        logger.warning("Zhipu API key not configured, returning empty tool list")
        return []

    return ZHIPU_SEARCH_TOOLS
