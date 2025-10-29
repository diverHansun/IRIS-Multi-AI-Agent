"""
DuckDuckGo Instant Answer API Tools Module

Provides instant answer functionality using DuckDuckGo Instant Answer API.
This API is completely free and does not require an API key.
"""

import json
import logging
import time
from typing import Annotated, Dict, Any, Optional, Tuple
from datetime import datetime

import requests
from requests.exceptions import RequestException, HTTPError

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


class SimpleCache:
    """Simple in-memory cache with expiration (reused from bing_search_tools)"""

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


class DuckDuckGoInstantProvider:
    """DuckDuckGo Instant Answer API provider"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize DuckDuckGo Instant Answer provider.

        Args:
            config_path: Path to config file, uses default if None
        """
        # Load configuration
        self.config = self._load_config(config_path)

        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Initialize cache if enabled
        self.cache = None
        if self.config.get("cache", {}).get("enable_cache", False):
            cache_expire = self.config["cache"].get("cache_expire_seconds", 3600)
            self.cache = SimpleCache(cache_expire)
            logger.info(f"Cache enabled with {cache_expire}s expiration")

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load DuckDuckGo configuration"""
        from pathlib import Path
        from .config import find_project_root

        if config_path is None:
            try:
                current_file = Path(__file__).resolve()
                project_root = find_project_root(current_file)
                config_path = project_root / "config" / "tools" / "sdk" / "search" / "duckduckgo.json"
            except Exception as e:
                logger.warning(f"Failed to find config file: {e}, using defaults")
                return self._get_default_config()
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            logger.warning(f"Config file not found at {config_path}, using defaults")
            return self._get_default_config()

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Loaded DuckDuckGo configuration from {config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "api": {
                "endpoint": "https://api.duckduckgo.com/",
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 1.0,
                "retry_backoff_factor": 2.0
            },
            "search": {
                "format": "json",
                "no_redirect": 1,
                "no_html": 1,
                "skip_disambig": 1
            },
            "cache": {
                "enable_cache": True,
                "cache_expire_seconds": 3600
            },
            "logging": {
                "enable_request_logging": True,
                "log_level": "INFO"
            }
        }

    def _make_request(self, params: Dict[str, Any]) -> requests.Response:
        """
        Make HTTP request to DuckDuckGo Instant Answer API with retry logic.

        Args:
            params: Query parameters

        Returns:
            Response object

        Raises:
            HTTPError: If request fails after retries
            RequestException: For other request errors
        """
        api_config = self.config.get("api", {})
        endpoint = api_config.get("endpoint", "https://api.duckduckgo.com/")
        timeout = api_config.get("timeout", 30)
        max_retries = api_config.get("max_retries", 3)
        retry_delay = api_config.get("retry_delay", 1.0)
        backoff_factor = api_config.get("retry_backoff_factor", 2.0)

        # Log request if enabled
        if self.config.get("logging", {}).get("enable_request_logging", True):
            logger.info(f"DuckDuckGo Instant Answer request: {params.get('q', 'N/A')}")
            logger.debug(f"Request endpoint: {endpoint}")
            logger.debug(f"Request params: {json.dumps(params, ensure_ascii=False)}")

        # Retry loop
        last_exception = None
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    endpoint,
                    params=params,
                    timeout=timeout
                )

                # Log response
                if self.config.get("logging", {}).get("enable_request_logging", True):
                    logger.debug(f"Response status: {response.status_code}")
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            f"Response body: {json.dumps(response.json(), ensure_ascii=False, indent=2)}"
                        )

                response.raise_for_status()
                return response

            except (HTTPError, RequestException) as e:
                last_exception = e
                wait_time = retry_delay * (backoff_factor ** attempt)
                logger.warning(
                    f"Request error: {str(e)}. "
                    f"Retry attempt {attempt + 1}/{max_retries} "
                    f"after {wait_time:.2f}s"
                )
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                continue

        logger.error(f"All retry attempts exhausted. Last error: {last_exception}")
        raise last_exception

    def _parse_response(self, query: str, response_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse DuckDuckGo Instant Answer API response.

        Args:
            query: Original search query
            response_json: Raw JSON response from API

        Returns:
            Formatted instant answer dictionary
        """
        result = {
            "query": query,
            "engine": "DuckDuckGo_Instant",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": response_json.get("Type", ""),
            "heading": response_json.get("Heading", ""),
            "abstract": response_json.get("AbstractText", ""),
            "abstract_source": response_json.get("AbstractSource", ""),
            "abstract_url": response_json.get("AbstractURL", ""),
            "image": response_json.get("Image", ""),
            "answer": response_json.get("Answer", ""),
            "answer_type": response_json.get("AnswerType", ""),
            "definition": response_json.get("Definition", ""),
            "definition_source": response_json.get("DefinitionSource", ""),
            "definition_url": response_json.get("DefinitionURL", ""),
            "related_topics": [],
            "results": []
        }

        # Extract related topics
        if "RelatedTopics" in response_json:
            for topic in response_json["RelatedTopics"]:
                if isinstance(topic, dict):
                    if "Text" in topic:
                        result["related_topics"].append({
                            "text": topic.get("Text", ""),
                            "url": topic.get("FirstURL", "")
                        })
                    elif "Topics" in topic:
                        # Nested topics
                        for subtopic in topic["Topics"]:
                            if "Text" in subtopic:
                                result["related_topics"].append({
                                    "text": subtopic.get("Text", ""),
                                    "url": subtopic.get("FirstURL", "")
                                })

        # Extract results
        if "Results" in response_json:
            result["results"] = response_json["Results"]

        return result

    def instant_answer(self, query: str) -> Dict[str, Any]:
        """
        Get instant answer from DuckDuckGo.

        Args:
            query: Search query string

        Returns:
            Formatted instant answer as dictionary

        Raises:
            ValueError: If query is empty
            HTTPError: If API request fails
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        query = query.strip()

        # Check cache if enabled
        if self.cache:
            cache_key = f"ddg_instant:{query}"
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                logger.info(f"Returning cached result for query: {query}")
                return cached_result

        # Prepare request parameters
        search_config = self.config.get("search", {})
        params = {
            "q": query,
            "format": search_config.get("format", "json"),
            "no_redirect": search_config.get("no_redirect", 1),
            "no_html": search_config.get("no_html", 1),
            "skip_disambig": search_config.get("skip_disambig", 1)
        }

        # Make API request
        logger.info(f"Querying DuckDuckGo Instant Answer for: {query}")
        response = self._make_request(params)

        # Parse response
        response_json = response.json()
        result = self._parse_response(query, response_json)

        # Cache result if enabled
        if self.cache:
            cache_key = f"ddg_instant:{query}"
            self.cache.set(cache_key, result)

        logger.info(
            f"Instant answer completed. "
            f"Type: {result['type']}, "
            f"Has abstract: {bool(result['abstract'])}, "
            f"Related topics: {len(result['related_topics'])}"
        )

        return result


# Global provider instance
_provider: Optional[DuckDuckGoInstantProvider] = None


def get_provider() -> DuckDuckGoInstantProvider:
    """Get global DuckDuckGoInstantProvider instance (singleton pattern)"""
    global _provider
    if _provider is None:
        _provider = DuckDuckGoInstantProvider()
    return _provider


@tool
def duckduckgo_instant_answer(query: Annotated[str, "Search query for instant answer (English only)"]) -> str:
    """
    Get instant answer from DuckDuckGo Instant Answer API

    IMPORTANT: This tool ONLY supports English queries and well-known entities.
    For Chinese queries or general searches, use web_search_basic instead.

    This tool provides quick answers, definitions, and summaries for well-known
    entities such as people, places, concepts, and terms (e.g., "Python programming language",
    "Albert Einstein", "Paris France").

    Language support: English only
    Best for: Famous people, places, programming languages, scientific concepts
    NOT suitable for: Chinese queries, unknown entities, recent news

    Args:
        query: Search query in English

    Returns:
        Instant answer as JSON string
    """
    try:
        provider = get_provider()
        result = provider.instant_answer(query)

        # Return formatted JSON string
        return json.dumps(result, ensure_ascii=False, indent=2)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({
            "error": "validation_error",
            "message": str(e),
            "query": query
        }, ensure_ascii=False, indent=2)

    except HTTPError as e:
        logger.error(f"HTTP error: {e}")
        return json.dumps({
            "error": "http_error",
            "message": str(e),
            "status_code": e.response.status_code if hasattr(e, 'response') else None,
            "query": query
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Unexpected error during DuckDuckGo instant answer: {e}", exc_info=True)
        return json.dumps({
            "error": "unexpected_error",
            "message": str(e),
            "query": query
        }, ensure_ascii=False, indent=2)


def get_available_tools():
    """
    Get available DuckDuckGo instant answer tools.

    Returns:
        List of tool functions
    """
    return [duckduckgo_instant_answer]


if __name__ == "__main__":
    # Simple test
    print("Testing DuckDuckGo Instant Answer API...")

    test_queries = [
        "Python programming language",
        "Elon Musk",
        "Paris France"
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        try:
            result = duckduckgo_instant_answer.func(query)
            result_dict = json.loads(result)
            print(f"Type: {result_dict.get('type', 'N/A')}")
            print(f"Heading: {result_dict.get('heading', 'N/A')}")
            print(f"Abstract: {result_dict.get('abstract', 'N/A')[:200]}...")
        except Exception as e:
            print(f"Error: {e}")
