"""
Zhipu Web Crawl Tool Module

Provides LangChain tool wrapper for Zhipu Reader API (/paas/v4/reader).
"""

import json
import logging
import time
import uuid
from typing import Annotated, Any, Dict, Optional, Tuple

import requests
from requests.exceptions import HTTPError, RequestException
from langchain_core.tools import tool

from .config import get_crawl_config

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
                logger.debug("Cache hit for key: %s", key)
                return value
            del self._cache[key]
            logger.debug("Cache expired for key: %s", key)
        return None

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = (value, time.time())
        logger.debug("Cache set for key: %s", key)

    def clear(self) -> None:
        self._cache.clear()
        logger.debug("Cache cleared")


class ZhipuCrawlProvider:
    """Zhipu Web Crawl API provider"""

    def __init__(self):
        self.config = get_crawl_config()
        self.session = requests.Session()

        self.cache = None
        if self.config.cache.enable_cache:
            self.cache = SimpleCache(self.config.cache.cache_expire_seconds)
            logger.info(
                "Crawl cache enabled with %ss expiration",
                self.config.cache.cache_expire_seconds,
            )

    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        return f"zhipu_crawl_{uuid.uuid4().hex}"

    def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to Zhipu Reader API with retry logic

        Args:
            payload: Request payload

        Returns:
            Response data dictionary

        Raises:
            HTTPError: If request fails after retries
            RequestException: For other request errors
        """
        if not self.config.is_available():
            raise ValueError(
                "Zhipu API key not configured. Please set ZHIPU_API_KEY environment variable."
            )

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        max_retries = self.config.api.max_retries
        retry_delay = self.config.api.retry_delay

        for attempt in range(max_retries + 1):
            try:
                response = self.session.post(
                    self.config.api.base_url,
                    json=payload,
                    headers=headers,
                    timeout=self.config.api.timeout,
                )
                response.raise_for_status()
                return response.json()
            except HTTPError as exc:
                if attempt < max_retries:
                    wait_time = retry_delay * (2**attempt)
                    logger.warning(
                        "Crawl request failed (attempt %d/%d): %s. Retrying in %ss...",
                        attempt + 1,
                        max_retries + 1,
                        exc,
                        wait_time,
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        "Crawl request failed after %d attempts: %s",
                        max_retries + 1,
                        exc,
                    )
                    raise
            except RequestException as exc:
                logger.error("Crawl request exception: %s", exc)
                raise

    def _validate_return_format(self, return_format: Optional[str]) -> str:
        """Validate return_format with fallback to config default"""
        if return_format in ("markdown", "text"):
            return return_format
        if return_format and return_format not in ("markdown", "text"):
            logger.warning(
                "Unsupported return_format '%s', falling back to default %s",
                return_format,
                self.config.crawl.return_format,
            )
        return self.config.crawl.return_format

    def _build_cache_key(self, url: str, return_format: str) -> str:
        """Build cache key incorporating key options"""
        return "crawl_{url}_{fmt}_{retain}_{imgsum}_{linksum}".format(
            url=url,
            fmt=return_format,
            retain=int(self.config.crawl.retain_images),
            imgsum=int(self.config.crawl.with_images_summary),
            linksum=int(self.config.crawl.with_links_summary),
        )

    def crawl(self, url: str, return_format: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform web crawl using Zhipu Reader API

        Args:
            url: Target URL
            return_format: Desired return format ("markdown" or "text")

        Returns:
            Dictionary containing crawl results
        """
        if not url or not url.strip():
            raise ValueError("URL is required for web crawl.")

        resolved_format = self._validate_return_format(return_format)

        payload = {
            "url": url.strip(),
            "timeout": self.config.crawl.timeout,
            "no_cache": self.config.crawl.no_cache,
            "return_format": resolved_format,
            "retain_images": self.config.crawl.retain_images,
            "no_gfm": self.config.crawl.no_gfm,
            "keep_img_data_url": self.config.crawl.keep_img_data_url,
            "with_images_summary": self.config.crawl.with_images_summary,
            "with_links_summary": self.config.crawl.with_links_summary,
            "request_id": self._generate_request_id(),
        }

        cache_key: Optional[str] = None
        if self.cache and not self.config.crawl.no_cache:
            cache_key = self._build_cache_key(payload["url"], resolved_format)
            cached_result = self.cache.get(cache_key)
            if cached_result:
                logger.info("Returning cached crawl result for url: %s", payload["url"])
                return cached_result

        try:
            logger.info("Executing Zhipu crawl for url: %s", payload["url"])
            result = self._make_request(payload)

            if self.cache and cache_key:
                self.cache.set(cache_key, result)

            return result
        except Exception as exc:
            logger.error("Zhipu crawl failed: %s", exc)
            return {"error": str(exc)}


_crawl_provider: Optional[ZhipuCrawlProvider] = None


def get_crawl_provider() -> ZhipuCrawlProvider:
    """Get global crawl provider instance (singleton pattern)"""
    global _crawl_provider
    if _crawl_provider is None:
        _crawl_provider = ZhipuCrawlProvider()
    return _crawl_provider


def format_crawl_result(result: Dict[str, Any]) -> str:
    """
    Format crawl results as JSON string for LLM consumption

    Args:
        result: Raw API response

    Returns:
        Formatted JSON string with crawl results
    """
    if "error" in result:
        return json.dumps(
            {"status": "error", "error": result["error"]},
            ensure_ascii=False,
            indent=2,
        )

    reader_result = result.get("reader_result", {}) or {}

    output = {
        "status": "success",
        "id": result.get("id", ""),
        "request_id": result.get("request_id", ""),
        "created": result.get("created", 0),
        "model": result.get("model", ""),
        "result": {
            "url": reader_result.get("url", ""),
            "title": reader_result.get("title", ""),
            "description": reader_result.get("description", ""),
            "content": reader_result.get("content", ""),
            "metadata": reader_result.get("metadata", {}),
            "external": reader_result.get("external", {}),
        },
    }

    return json.dumps(output, ensure_ascii=False, indent=2)


@tool
def zhipu_web_crawl(
    url: Annotated[str, "Target URL to read and parse"],
    return_format: Annotated[
        Optional[str], "Return format: markdown (default) or text"
    ] = None,
) -> str:
    """
    Read and parse a web page using Zhipu Reader API.

    Only exposes url and optional return_format; other crawl options are configured in
    config/tools/sdk/zhipu/zhipu_crawl.json.

    Args:
        url: Target URL to fetch
        return_format: Optional return format override ("markdown" or "text")

    Returns:
        JSON string containing crawl result or error details
    """
    try:
        provider = get_crawl_provider()

        if not provider.config.is_available():
            return json.dumps(
                {
                    "status": "error",
                    "error": "Zhipu API key not configured. Please set ZHIPU_API_KEY environment variable.",
                },
                ensure_ascii=False,
                indent=2,
            )

        result = provider.crawl(url, return_format)
        return format_crawl_result(result)
    except Exception as exc:
        logger.error("Zhipu web crawl tool execution failed: %s", exc)
        return json.dumps(
            {"status": "error", "error": f"Crawl execution failed: {str(exc)}"},
            ensure_ascii=False,
            indent=2,
        )


ZHIPU_CRAWL_TOOLS = [zhipu_web_crawl]
