"""
Tavily Search Configuration Module

Manages configuration for Tavily API including Search, Extract, Map, and Crawl operations.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass, field
from pathlib import Path

from src.core.config import ensure_initialized, get_config_loader

logger = logging.getLogger(__name__)


@dataclass
class TavilyAPIConfig:
    """Tavily API configuration"""
    base_url: str = "https://api.tavily.com"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class TavilySearchConfig:
    """Tavily Search configuration"""
    max_results: int = 5
    search_depth: Literal["basic", "advanced"] = "basic"
    topic: Literal["general", "news", "finance"] = "general"
    include_answer: bool = False
    include_raw_content: bool = False
    include_images: bool = False
    include_image_descriptions: bool = False
    include_favicon: bool = False
    time_range: Optional[Literal["day", "week", "month", "year"]] = None
    country: Optional[str] = None
    auto_parameters: bool = False


@dataclass
class TavilyExtractConfig:
    """Tavily Extract configuration"""
    extract_depth: Literal["basic", "advanced"] = "basic"
    include_images: bool = False
    include_favicon: bool = False
    format: Literal["markdown", "text"] = "markdown"


@dataclass
class TavilyMapConfig:
    """Tavily Map configuration"""
    max_depth: int = 1
    max_breadth: int = 20
    limit: int = 50
    allow_external: bool = False
    categories: Optional[List[str]] = None


@dataclass
class TavilyCrawlConfig:
    """Tavily Crawl configuration"""
    max_depth: int = 1
    max_breadth: int = 20
    limit: int = 50
    allow_external: bool = False
    include_images: bool = False
    extract_depth: Literal["basic", "advanced"] = "basic"
    include_favicon: bool = False
    format: Literal["markdown", "text"] = "markdown"
    categories: Optional[List[str]] = None


@dataclass
class TavilyRateLimitConfig:
    """Rate limiting configuration"""
    requests_per_minute: int = 60
    enable_rate_limiting: bool = True


@dataclass
class TavilyCacheConfig:
    """Cache configuration"""
    enable_cache: bool = False
    cache_expire_seconds: int = 300


@dataclass
class TavilyConfig:
    """Complete Tavily configuration"""
    api: TavilyAPIConfig = field(default_factory=TavilyAPIConfig)
    search: TavilySearchConfig = field(default_factory=TavilySearchConfig)
    extract: TavilyExtractConfig = field(default_factory=TavilyExtractConfig)
    map: TavilyMapConfig = field(default_factory=TavilyMapConfig)
    crawl: TavilyCrawlConfig = field(default_factory=TavilyCrawlConfig)
    rate_limit: TavilyRateLimitConfig = field(default_factory=TavilyRateLimitConfig)
    cache: TavilyCacheConfig = field(default_factory=TavilyCacheConfig)

    api_key: Optional[str] = None

    def __post_init__(self):
        """Post-initialization validation and setup"""
        # Load API key from environment if not provided
        if not self.api_key:
            self.api_key = os.getenv("TAVILY_API_KEY")

        # Validate configurations
        self._validate_config()

    def _validate_config(self):
        """Validate configuration values"""
        # Validate API config
        if self.api.timeout <= 0:
            logger.warning("Invalid timeout value, resetting to 30")
            self.api.timeout = 30

        if self.api.max_retries < 0:
            logger.warning("Invalid max_retries value, resetting to 3")
            self.api.max_retries = 3

        # Validate Search config
        if self.search.max_results <= 0 or self.search.max_results > 20:
            logger.warning("Invalid max_results, must be between 1-20, resetting to 5")
            self.search.max_results = 5

        # Validate Map config
        if self.map.max_depth <= 0:
            logger.warning("Invalid map max_depth, resetting to 1")
            self.map.max_depth = 1

        if self.map.max_breadth <= 0:
            logger.warning("Invalid map max_breadth, resetting to 20")
            self.map.max_breadth = 20

        if self.map.limit <= 0:
            logger.warning("Invalid map limit, resetting to 50")
            self.map.limit = 50

        # Validate Crawl config
        if self.crawl.max_depth <= 0:
            logger.warning("Invalid crawl max_depth, resetting to 1")
            self.crawl.max_depth = 1

        if self.crawl.max_breadth <= 0:
            logger.warning("Invalid crawl max_breadth, resetting to 20")
            self.crawl.max_breadth = 20

        if self.crawl.limit <= 0:
            logger.warning("Invalid crawl limit, resetting to 50")
            self.crawl.limit = 50

    def is_available(self) -> bool:
        """Check if Tavily API is available (API key configured)"""
        return bool(self.api_key and len(self.api_key.strip()) > 0)


def _load_json_with_loader(
    default_relative_path: str, config_path: Optional[str]
) -> Dict[str, Any]:
    """
    Load JSON configuration via shared ConfigLoader with optional explicit path.
    """
    if config_path:
        path_obj = Path(config_path)
        if not path_obj.exists():
            logger.warning("Config file not found at %s, using defaults", path_obj)
            return {}
        try:
            with open(path_obj, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load config from %s: %s", path_obj, e)
            return {}

    ensure_initialized(quiet=True)
    loader = get_config_loader()
    data = loader.load_shared_json(default_relative_path)
    if data is None:
        logger.warning(
            "Config %s not found in .iris or bundled defaults, using empty config",
            default_relative_path,
        )
        return {}
    return data


def load_config_from_json(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from JSON file

    Args:
        config_path: Path to config file, defaults to config/tools/sdk/tavily/config.json

    Returns:
        Dictionary with configuration values
    """
    config_data = _load_json_with_loader("tools/sdk/tavily.json", config_path)
    if config_path:
        logger.info("Loaded Tavily configuration from %s", config_path)
    return config_data


def load_config_from_env() -> TavilyConfig:
    """
    Load configuration from environment variables and JSON file

    Returns:
        TavilyConfig instance
    """
    # Load base configuration from JSON
    json_config = load_config_from_json()

    # Create config objects
    api_config = TavilyAPIConfig(
        base_url=os.getenv("TAVILY_BASE_URL", json_config.get("api", {}).get("base_url", "https://api.tavily.com")),
        timeout=int(os.getenv("TAVILY_TIMEOUT", json_config.get("api", {}).get("timeout", 30))),
        max_retries=int(os.getenv("TAVILY_MAX_RETRIES", json_config.get("api", {}).get("max_retries", 3))),
        retry_delay=float(os.getenv("TAVILY_RETRY_DELAY", json_config.get("api", {}).get("retry_delay", 1.0)))
    )

    search_config_data = json_config.get("search", {})
    search_config = TavilySearchConfig(
        max_results=int(os.getenv("TAVILY_SEARCH_MAX_RESULTS", search_config_data.get("max_results", 5))),
        search_depth=os.getenv("TAVILY_SEARCH_DEPTH", search_config_data.get("search_depth", "basic")),
        topic=os.getenv("TAVILY_SEARCH_TOPIC", search_config_data.get("topic", "general")),
        include_answer=os.getenv("TAVILY_SEARCH_INCLUDE_ANSWER", str(search_config_data.get("include_answer", False))).lower() in ("true", "1", "yes"),
        include_raw_content=os.getenv("TAVILY_SEARCH_INCLUDE_RAW_CONTENT", str(search_config_data.get("include_raw_content", False))).lower() in ("true", "1", "yes"),
        include_images=os.getenv("TAVILY_SEARCH_INCLUDE_IMAGES", str(search_config_data.get("include_images", False))).lower() in ("true", "1", "yes"),
        include_image_descriptions=os.getenv("TAVILY_SEARCH_INCLUDE_IMAGE_DESCRIPTIONS", str(search_config_data.get("include_image_descriptions", False))).lower() in ("true", "1", "yes"),
        include_favicon=os.getenv("TAVILY_SEARCH_INCLUDE_FAVICON", str(search_config_data.get("include_favicon", False))).lower() in ("true", "1", "yes"),
        auto_parameters=os.getenv("TAVILY_SEARCH_AUTO_PARAMETERS", str(search_config_data.get("auto_parameters", False))).lower() in ("true", "1", "yes")
    )

    extract_config_data = json_config.get("extract", {})
    extract_config = TavilyExtractConfig(
        extract_depth=os.getenv("TAVILY_EXTRACT_DEPTH", extract_config_data.get("extract_depth", "basic")),
        include_images=os.getenv("TAVILY_EXTRACT_INCLUDE_IMAGES", str(extract_config_data.get("include_images", False))).lower() in ("true", "1", "yes"),
        include_favicon=os.getenv("TAVILY_EXTRACT_INCLUDE_FAVICON", str(extract_config_data.get("include_favicon", False))).lower() in ("true", "1", "yes"),
        format=os.getenv("TAVILY_EXTRACT_FORMAT", extract_config_data.get("format", "markdown"))
    )

    map_config_data = json_config.get("map", {})
    map_config = TavilyMapConfig(
        max_depth=int(os.getenv("TAVILY_MAP_MAX_DEPTH", map_config_data.get("max_depth", 1))),
        max_breadth=int(os.getenv("TAVILY_MAP_MAX_BREADTH", map_config_data.get("max_breadth", 20))),
        limit=int(os.getenv("TAVILY_MAP_LIMIT", map_config_data.get("limit", 50))),
        allow_external=os.getenv("TAVILY_MAP_ALLOW_EXTERNAL", str(map_config_data.get("allow_external", False))).lower() in ("true", "1", "yes")
    )

    crawl_config_data = json_config.get("crawl", {})
    crawl_config = TavilyCrawlConfig(
        max_depth=int(os.getenv("TAVILY_CRAWL_MAX_DEPTH", crawl_config_data.get("max_depth", 1))),
        max_breadth=int(os.getenv("TAVILY_CRAWL_MAX_BREADTH", crawl_config_data.get("max_breadth", 20))),
        limit=int(os.getenv("TAVILY_CRAWL_LIMIT", crawl_config_data.get("limit", 50))),
        allow_external=os.getenv("TAVILY_CRAWL_ALLOW_EXTERNAL", str(crawl_config_data.get("allow_external", False))).lower() in ("true", "1", "yes"),
        include_images=os.getenv("TAVILY_CRAWL_INCLUDE_IMAGES", str(crawl_config_data.get("include_images", False))).lower() in ("true", "1", "yes"),
        extract_depth=os.getenv("TAVILY_CRAWL_EXTRACT_DEPTH", crawl_config_data.get("extract_depth", "basic")),
        include_favicon=os.getenv("TAVILY_CRAWL_INCLUDE_FAVICON", str(crawl_config_data.get("include_favicon", False))).lower() in ("true", "1", "yes"),
        format=os.getenv("TAVILY_CRAWL_FORMAT", crawl_config_data.get("format", "markdown"))
    )

    rate_limit_config_data = json_config.get("rate_limit", {})
    rate_limit_config = TavilyRateLimitConfig(
        requests_per_minute=int(os.getenv("TAVILY_RATE_LIMIT_RPM", rate_limit_config_data.get("requests_per_minute", 60))),
        enable_rate_limiting=os.getenv("TAVILY_ENABLE_RATE_LIMITING", str(rate_limit_config_data.get("enable_rate_limiting", True))).lower() in ("true", "1", "yes")
    )

    cache_config_data = json_config.get("cache", {})
    cache_config = TavilyCacheConfig(
        enable_cache=os.getenv("TAVILY_ENABLE_CACHE", str(cache_config_data.get("enable_cache", False))).lower() in ("true", "1", "yes"),
        cache_expire_seconds=int(os.getenv("TAVILY_CACHE_EXPIRE_SECONDS", cache_config_data.get("cache_expire_seconds", 300)))
    )

    # Get API key from environment
    api_key = os.getenv("TAVILY_API_KEY")

    return TavilyConfig(
        api=api_config,
        search=search_config,
        extract=extract_config,
        map=map_config,
        crawl=crawl_config,
        rate_limit=rate_limit_config,
        cache=cache_config,
        api_key=api_key
    )


# Global configuration instance
_global_config: Optional[TavilyConfig] = None


def get_config() -> TavilyConfig:
    """
    Get global Tavily configuration instance (singleton pattern)

    Returns:
        TavilyConfig instance
    """
    global _global_config
    if _global_config is None:
        _global_config = load_config_from_env()
    return _global_config


def set_config(config: TavilyConfig) -> None:
    """
    Set global configuration instance

    Args:
        config: TavilyConfig instance to set as global
    """
    global _global_config
    _global_config = config


def reset_config() -> None:
    """Reset global configuration to reload from environment"""
    global _global_config
    _global_config = None


def get_config_summary() -> Dict[str, Any]:
    """
    Get configuration summary

    Returns:
        Dictionary with configuration summary
    """
    config = get_config()

    return {
        "api_available": config.is_available(),
        "api_config": {
            "base_url": config.api.base_url,
            "timeout": config.api.timeout,
            "max_retries": config.api.max_retries
        },
        "search_defaults": {
            "max_results": config.search.max_results,
            "search_depth": config.search.search_depth,
            "topic": config.search.topic
        },
        "extract_defaults": {
            "extract_depth": config.extract.extract_depth,
            "format": config.extract.format
        },
        "map_defaults": {
            "max_depth": config.map.max_depth,
            "max_breadth": config.map.max_breadth,
            "limit": config.map.limit
        },
        "crawl_defaults": {
            "max_depth": config.crawl.max_depth,
            "max_breadth": config.crawl.max_breadth,
            "limit": config.crawl.limit,
            "format": config.crawl.format
        },
        "rate_limit": {
            "enabled": config.rate_limit.enable_rate_limiting,
            "requests_per_minute": config.rate_limit.requests_per_minute
        },
        "cache": {
            "enabled": config.cache.enable_cache,
            "expire_seconds": config.cache.cache_expire_seconds
        }
    }
