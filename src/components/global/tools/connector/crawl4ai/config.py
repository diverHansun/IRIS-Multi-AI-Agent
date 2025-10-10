"""
Configuration module for Crawl4AI connector
"""

import os
import json
from typing import Optional, List, Dict, Union
from pathlib import Path


class Crawl4AIConfig:
    """Configuration for Crawl4AI connector"""
    
    def __init__(self, config_path: Optional[str] = None):
        # Load from JSON config file if available
        self.config_path = config_path or self._find_config_file()
        self._load_config_from_file()
        
        # Override with environment variables if present
        self._apply_env_overrides()
    
    def _find_config_file(self):
        """Find the config file in the standard locations"""
        possible_paths = [
            os.getenv("CRAWL4AI_CONFIG_PATH"),
            "config/connector/crawl4ai/config.json",
        ]
        
        for path in possible_paths:
            if path and os.path.exists(path):
                return path
        return None
    
    def _load_config_from_file(self):
        """Load configuration from the JSON file"""
        if self.config_path and os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Set default values
            default_config = config_data.get("default", {})
            self.base_url: str = default_config.get("base_url", "http://localhost:11235")
            self.timeout: int = default_config.get("timeout", 60)
            self.stream_timeout: int = default_config.get("stream_timeout", 120)
            self.retry_attempts: int = default_config.get("retry_attempts", 2)
            self.token: Optional[str] = default_config.get("token")
            
            # Set browser configuration (BrowserConfig parameters)
            self.browser_config: Dict = config_data.get("browser", {})

            # Set crawler configuration (CrawlerRunConfig parameters)
            self.crawler_config: Dict = config_data.get("crawler", {})

            # Set additional configurations (reserved for future expansion)
            self.http_config: Dict = config_data.get("http", {})
            self.geolocation_config: Dict = config_data.get("geolocation", {})
            self.proxy_config: Dict = config_data.get("proxy", {})
            self.virtual_scroll_config: Dict = config_data.get("virtual_scroll", {})
            self.link_preview_config: Dict = config_data.get("link_preview", {})
            self.llm_config: Dict = config_data.get("llm", {})
            self.seeding_config: Dict = config_data.get("seeding", {})

            # Set return format (commonly used parameter)
            self.return_format: str = self.crawler_config.get("return_format", "markdown")  # Default to markdown
        else:
            # Fallback to environment variables or defaults
            self.base_url: str = os.getenv("CRAWL4AI_BASE_URL", "http://localhost:11235")
            self.timeout: int = int(os.getenv("CRAWL4AI_TIMEOUT", "60"))
            self.stream_timeout: int = int(os.getenv("CRAWL4AI_STREAM_TIMEOUT", "120"))
            self.token: Optional[str] = os.getenv("CRAWL4AI_TOKEN")
            self.retry_attempts: int = int(os.getenv("CRAWL4AI_RETRY_ATTEMPTS", "2"))
            self.return_format: str = os.getenv("CRAWL4AI_RETURN_FORMAT", "markdown")  # Default to markdown
            # Initialize config dicts as empty
            self.browser_config: Dict = {}
            self.crawler_config: Dict = {}
            self.http_config: Dict = {}
            self.geolocation_config: Dict = {}
            self.proxy_config: Dict = {}
            self.virtual_scroll_config: Dict = {}
            self.link_preview_config: Dict = {}
            self.llm_config: Dict = {}
            self.seeding_config: Dict = {}
    
    def _apply_env_overrides(self):
        """Override config values with environment variables"""
        self.base_url = os.getenv("CRAWL4AI_BASE_URL", self.base_url)
        self.timeout = int(os.getenv("CRAWL4AI_TIMEOUT", str(self.timeout)))
        self.stream_timeout = int(os.getenv("CRAWL4AI_STREAM_TIMEOUT", str(self.stream_timeout)))
        self.token = os.getenv("CRAWL4AI_TOKEN", self.token)
        self.retry_attempts = int(os.getenv("CRAWL4AI_RETRY_ATTEMPTS", str(self.retry_attempts)))
        self.return_format = os.getenv("CRAWL4AI_RETURN_FORMAT", self.return_format)