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
            
            # Set crawl-specific values based on actual Crawl4AI parameters
            crawl_config = config_data.get("crawl", {})
            self.word_count_threshold: int = crawl_config.get("word_count_threshold", 200)
            self.only_text: bool = crawl_config.get("only_text", True)
            self.css_selector: Optional[str] = crawl_config.get("css_selector")
            self.target_elements: List[str] = crawl_config.get("target_elements", [])
            self.excluded_tags: List[str] = crawl_config.get("excluded_tags", ["nav", "footer", "aside", "script", "style"])
            self.excluded_selector: str = crawl_config.get("excluded_selector", "")
            self.remove_forms: bool = crawl_config.get("remove_forms", False)
            self.prettiify: bool = crawl_config.get("prettiify", False)
            self.parser_type: str = crawl_config.get("parser_type", "lxml")
            self.wait_until: str = crawl_config.get("wait_until", "domcontentloaded")
            self.page_timeout: int = crawl_config.get("page_timeout", 60000)
            self.wait_for: Optional[str] = crawl_config.get("wait_for")
            self.wait_for_timeout: Optional[int] = crawl_config.get("wait_for_timeout")
            self.delay_before_return_html: float = crawl_config.get("delay_before_return_html", 0.1)
            self.scan_full_page: bool = crawl_config.get("scan_full_page", False)
            self.scroll_delay: float = crawl_config.get("scroll_delay", 0.2)
            self.process_iframes: bool = crawl_config.get("process_iframes", False)
            self.remove_overlay_elements: bool = crawl_config.get("remove_overlay_elements", False)
            self.simulate_user: bool = crawl_config.get("simulate_user", False)
            self.screenshot: bool = crawl_config.get("screenshot", False)
            self.screenshot_wait_for: Optional[float] = crawl_config.get("screenshot_wait_for")
            self.pdf: bool = crawl_config.get("pdf", False)
            self.exclude_external_images: bool = crawl_config.get("exclude_external_images", False)
            self.exclude_all_images: bool = crawl_config.get("exclude_all_images", False)
            self.table_score_threshold: int = crawl_config.get("table_score_threshold", 7)
            self.cache_mode: str = crawl_config.get("cache_mode", "bypass")
            self.exclude_external_links: bool = crawl_config.get("exclude_external_links", False)
            self.exclude_social_media_links: bool = crawl_config.get("exclude_social_media_links", False)
            self.exclude_domains: List[str] = crawl_config.get("exclude_domains", [])
            self.verbose: bool = crawl_config.get("verbose", True)
            self.js_code: Optional[Union[str, List[str]]] = crawl_config.get("js_code")
            self.wait_for_images: bool = crawl_config.get("wait_for_images", False)
            self.ignore_body_visibility: bool = crawl_config.get("ignore_body_visibility", True)
            self.max_scroll_steps: Optional[int] = crawl_config.get("max_scroll_steps")
            self.override_navigator: bool = crawl_config.get("override_navigator", False)
            self.magic: bool = crawl_config.get("magic", False)
            self.adjust_viewport_to_content: bool = crawl_config.get("adjust_viewport_to_content", False)
            self.return_format: str = crawl_config.get("return_format", "markdown")  # Default to markdown

            # LLM-focused parameters
            self.content_filter_type: Optional[str] = crawl_config.get("content_filter_type")
            self.pruning_threshold: Optional[float] = crawl_config.get("pruning_threshold")
            self.pruning_threshold_type: Optional[str] = crawl_config.get("pruning_threshold_type")
            self.min_word_threshold: Optional[int] = crawl_config.get("min_word_threshold")
            self.bm25_threshold: Optional[float] = crawl_config.get("bm25_threshold")
            self.user_query: Optional[str] = crawl_config.get("user_query")
            self.max_token_length: Optional[int] = crawl_config.get("max_token_length")
            self.prefer_fit_markdown: Optional[bool] = crawl_config.get("prefer_fit_markdown")
            self.extract_main_content: Optional[bool] = crawl_config.get("extract_main_content")
        else:
            # Fallback to environment variables or defaults
            self.base_url: str = os.getenv("CRAWL4AI_BASE_URL", "http://localhost:11235")
            self.timeout: int = int(os.getenv("CRAWL4AI_TIMEOUT", "60"))
            self.stream_timeout: int = int(os.getenv("CRAWL4AI_STREAM_TIMEOUT", "120"))
            self.token: Optional[str] = os.getenv("CRAWL4AI_TOKEN")
            self.retry_attempts: int = int(os.getenv("CRAWL4AI_RETRY_ATTEMPTS", "2"))
            self.return_format: str = os.getenv("CRAWL4AI_RETURN_FORMAT", "markdown")  # Default to markdown
    
    def _apply_env_overrides(self):
        """Override config values with environment variables"""
        self.base_url = os.getenv("CRAWL4AI_BASE_URL", self.base_url)
        self.timeout = int(os.getenv("CRAWL4AI_TIMEOUT", str(self.timeout)))
        self.stream_timeout = int(os.getenv("CRAWL4AI_STREAM_TIMEOUT", str(self.stream_timeout)))
        self.token = os.getenv("CRAWL4AI_TOKEN", self.token)
        self.retry_attempts = int(os.getenv("CRAWL4AI_RETRY_ATTEMPTS", str(self.retry_attempts)))
        self.return_format = os.getenv("CRAWL4AI_RETURN_FORMAT", self.return_format)