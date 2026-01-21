"""
Zhipu Web Search Configuration Module

Manages configuration for Zhipu Web Search API.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from pathlib import Path

from src.core.config import ensure_initialized, get_config_loader

logger = logging.getLogger(__name__)


@dataclass
class ZhipuAPIConfig:
    """Zhipu API configuration"""
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/web_search"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class ZhipuSearchConfig:
    """Zhipu Search default configuration"""
    search_engine: Literal["search_std", "search_pro", "search_pro_sogou", "search_pro_quark"] = "search_pro"
    search_intent: bool = False
    count: int = 10
    search_recency_filter: Literal["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"] = "noLimit"
    content_size: Literal["medium", "high"] = "medium"
    search_domain_filter: str = ""


@dataclass
class ZhipuCacheConfig:
    """Cache configuration"""
    enable_cache: bool = False
    cache_expire_seconds: int = 300


@dataclass
class ZhipuCrawlAPIConfig:
    """Zhipu Crawl API configuration"""
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/reader"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class ZhipuCrawlRequestConfig:
    """Zhipu Crawl request defaults"""
    timeout: int = 20
    no_cache: bool = False
    return_format: Literal["markdown", "text"] = "markdown"
    retain_images: bool = True
    no_gfm: bool = False
    keep_img_data_url: bool = False
    with_images_summary: bool = False
    with_links_summary: bool = False


@dataclass
class ZhipuCrawlCacheConfig:
    """Crawl cache configuration"""
    enable_cache: bool = False
    cache_expire_seconds: int = 300


@dataclass
class ZhipuConfig:
    """Complete Zhipu configuration"""
    api: ZhipuAPIConfig = field(default_factory=ZhipuAPIConfig)
    search: ZhipuSearchConfig = field(default_factory=ZhipuSearchConfig)
    cache: ZhipuCacheConfig = field(default_factory=ZhipuCacheConfig)

    api_key: Optional[str] = None

    def __post_init__(self):
        """Post-initialization validation and setup"""
        # Load API key from environment if not provided
        if not self.api_key:
            self.api_key = os.getenv("ZHIPU_API_KEY")

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
        if self.search.count <= 0 or self.search.count > 50:
            logger.warning("Invalid count, must be between 1-50, resetting to 10")
            self.search.count = 10

        # Validate Cache config
        if self.cache.cache_expire_seconds <= 0:
            logger.warning("Invalid cache_expire_seconds, resetting to 300")
        self.cache.cache_expire_seconds = 300

    def is_available(self) -> bool:
        """Check if Zhipu API is available (API key configured)"""
        return bool(self.api_key and len(self.api_key.strip()) > 0)


@dataclass
class ZhipuCrawlConfig:
    """Complete Zhipu Crawl configuration"""
    api: ZhipuCrawlAPIConfig = field(default_factory=ZhipuCrawlAPIConfig)
    crawl: ZhipuCrawlRequestConfig = field(default_factory=ZhipuCrawlRequestConfig)
    cache: ZhipuCrawlCacheConfig = field(default_factory=ZhipuCrawlCacheConfig)

    api_key: Optional[str] = None

    def __post_init__(self):
        """Post-initialization validation and setup"""
        if not self.api_key:
            self.api_key = os.getenv("ZHIPU_API_KEY")
        self._validate_config()

    def _validate_config(self):
        """Validate configuration values"""
        if self.api.timeout <= 0:
            logger.warning("Invalid crawl API timeout, resetting to 30")
            self.api.timeout = 30
        if self.api.max_retries < 0:
            logger.warning("Invalid crawl API max_retries, resetting to 3")
            self.api.max_retries = 3
        if self.crawl.timeout <= 0:
            logger.warning("Invalid crawl timeout, resetting to 20")
            self.crawl.timeout = 20
        if self.crawl.return_format not in ("markdown", "text"):
            logger.warning("Invalid return_format, resetting to markdown")
            self.crawl.return_format = "markdown"
        if self.cache.cache_expire_seconds <= 0:
            logger.warning("Invalid crawl cache_expire_seconds, resetting to 300")
            self.cache.cache_expire_seconds = 300

    def is_available(self) -> bool:
        """Check if Zhipu Crawl API is available (API key configured)"""
        return bool(self.api_key and len(self.api_key.strip()) > 0)


def _load_json_with_loader(
    default_relative_path: str, config_path: Optional[str]
) -> Dict[str, Any]:
    """
    Load JSON configuration using shared .iris (project/user) with bundled fallback.
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
        config_path: Path to config file, defaults to config/tools/sdk/zhipu/zhipu_search.json

    Returns:
        Dictionary with configuration values
    """
    config_data = _load_json_with_loader("tools/sdk/zhipu_search.json", config_path)
    if config_path:
        logger.info("Loaded Zhipu configuration from %s", config_path)
    return config_data


def load_config_from_env() -> ZhipuConfig:
    """
    Load configuration from environment variables and JSON file

    Returns:
        ZhipuConfig instance
    """
    # Load base configuration from JSON
    json_config = load_config_from_json()

    # Create config objects
    api_config = ZhipuAPIConfig(
        base_url=json_config.get("api", {}).get("base_url", "https://open.bigmodel.cn/api/paas/v4/web_search"),
        timeout=int(json_config.get("api", {}).get("timeout", 30)),
        max_retries=int(json_config.get("api", {}).get("max_retries", 3)),
        retry_delay=float(json_config.get("api", {}).get("retry_delay", 1.0))
    )

    search_config_data = json_config.get("search", {})
    search_config = ZhipuSearchConfig(
        search_engine=search_config_data.get("search_engine", "search_pro"),
        search_intent=search_config_data.get("search_intent", False),
        count=int(search_config_data.get("count", 10)),
        search_recency_filter=search_config_data.get("search_recency_filter", "noLimit"),
        content_size=search_config_data.get("content_size", "medium"),
        search_domain_filter=search_config_data.get("search_domain_filter", "")
    )

    cache_config_data = json_config.get("cache", {})
    cache_config = ZhipuCacheConfig(
        enable_cache=cache_config_data.get("enable_cache", False),
        cache_expire_seconds=int(cache_config_data.get("cache_expire_seconds", 300))
    )

    # Get API key from environment
    api_key = os.getenv("ZHIPU_API_KEY")

    return ZhipuConfig(
        api=api_config,
        search=search_config,
        cache=cache_config,
        api_key=api_key
    )


def load_crawl_config_from_json(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load crawl configuration from JSON file

    Args:
        config_path: Path to config file, defaults to config/tools/sdk/zhipu/zhipu_crawl.json

    Returns:
        Dictionary with configuration values
    """
    config_data = _load_json_with_loader("tools/sdk/zhipu_crawl.json", config_path)
    if config_path:
        logger.info("Loaded Zhipu crawl configuration from %s", config_path)
    return config_data


def load_crawl_config_from_env() -> ZhipuCrawlConfig:
    """
    Load crawl configuration from environment variables and JSON file

    Returns:
        ZhipuCrawlConfig instance
    """
    json_config = load_crawl_config_from_json()

    api_config = ZhipuCrawlAPIConfig(
        base_url=json_config.get("api", {}).get("base_url", "https://open.bigmodel.cn/api/paas/v4/reader"),
        timeout=int(json_config.get("api", {}).get("timeout", 30)),
        max_retries=int(json_config.get("api", {}).get("max_retries", 3)),
        retry_delay=float(json_config.get("api", {}).get("retry_delay", 1.0)),
    )

    crawl_data = json_config.get("crawl", {})
    crawl_config = ZhipuCrawlRequestConfig(
        timeout=int(crawl_data.get("timeout", 20)),
        no_cache=crawl_data.get("no_cache", False),
        return_format=crawl_data.get("return_format", "markdown"),
        retain_images=crawl_data.get("retain_images", True),
        no_gfm=crawl_data.get("no_gfm", False),
        keep_img_data_url=crawl_data.get("keep_img_data_url", False),
        with_images_summary=crawl_data.get("with_images_summary", False),
        with_links_summary=crawl_data.get("with_links_summary", False),
    )

    cache_data = json_config.get("cache", {})
    cache_config = ZhipuCrawlCacheConfig(
        enable_cache=cache_data.get("enable_cache", False),
        cache_expire_seconds=int(cache_data.get("cache_expire_seconds", 300)),
    )

    api_key = os.getenv("ZHIPU_API_KEY")

    return ZhipuCrawlConfig(
        api=api_config,
        crawl=crawl_config,
        cache=cache_config,
        api_key=api_key,
    )


# Global configuration instance
_global_config: Optional[ZhipuConfig] = None
_global_crawl_config: Optional[ZhipuCrawlConfig] = None


def get_config() -> ZhipuConfig:
    """
    Get global Zhipu configuration instance (singleton pattern)

    Returns:
        ZhipuConfig instance
    """
    global _global_config
    if _global_config is None:
        _global_config = load_config_from_env()
    return _global_config


def set_config(config: ZhipuConfig) -> None:
    """
    Set global configuration instance

    Args:
        config: ZhipuConfig instance to set as global
    """
    global _global_config
    _global_config = config


def reset_config() -> None:
    """Reset global configuration to reload from environment"""
    global _global_config
    _global_config = None


def get_crawl_config() -> ZhipuCrawlConfig:
    """
    Get global Zhipu Crawl configuration instance (singleton pattern)

    Returns:
        ZhipuCrawlConfig instance
    """
    global _global_crawl_config
    if _global_crawl_config is None:
        _global_crawl_config = load_crawl_config_from_env()
    return _global_crawl_config


def set_crawl_config(config: ZhipuCrawlConfig) -> None:
    """
    Set global crawl configuration instance

    Args:
        config: ZhipuCrawlConfig instance to set as global
    """
    global _global_crawl_config
    _global_crawl_config = config


def reset_crawl_config() -> None:
    """Reset global crawl configuration to reload from environment"""
    global _global_crawl_config
    _global_crawl_config = None


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
            "search_engine": config.search.search_engine,
            "search_intent": config.search.search_intent,
            "count": config.search.count,
            "search_recency_filter": config.search.search_recency_filter,
            "content_size": config.search.content_size,
            "search_domain_filter": config.search.search_domain_filter
        },
        "cache": {
            "enabled": config.cache.enable_cache,
            "expire_seconds": config.cache.cache_expire_seconds
        }
    }


def get_crawl_config_summary() -> Dict[str, Any]:
    """
    Get crawl configuration summary

    Returns:
        Dictionary with configuration summary
    """
    config = get_crawl_config()

    return {
        "api_available": config.is_available(),
        "api_config": {
            "base_url": config.api.base_url,
            "timeout": config.api.timeout,
            "max_retries": config.api.max_retries,
        },
        "crawl_defaults": {
            "timeout": config.crawl.timeout,
            "return_format": config.crawl.return_format,
            "retain_images": config.crawl.retain_images,
            "with_images_summary": config.crawl.with_images_summary,
            "with_links_summary": config.crawl.with_links_summary,
            "no_cache": config.crawl.no_cache,
            "no_gfm": config.crawl.no_gfm,
            "keep_img_data_url": config.crawl.keep_img_data_url,
        },
        "cache": {
            "enabled": config.cache.enable_cache,
            "expire_seconds": config.cache.cache_expire_seconds,
        },
    }
