"""
LangChain tools for Crawl4AI connector
"""

import json
from typing import Any, Dict, List, Optional, Union
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from .client import Crawl4AIClient
from .config import Crawl4AIConfig


class Crawl4AICrawlInput(BaseModel):
    """Input for Crawl4AI crawl tool."""
    
    urls: List[str] = Field(..., description="List of URLs to crawl")
    word_count_threshold: Optional[int] = Field(default=None, description="Minimum word count threshold before processing content")
    only_text: Optional[bool] = Field(default=None, description="If True, attempt to extract text-only content")
    css_selector: Optional[str] = Field(default=None, description="CSS selector to extract a specific portion of the page")
    target_elements: Optional[List[str]] = Field(default=None, description="List of CSS selectors for specific elements for Markdown generation")
    excluded_tags: Optional[List[str]] = Field(default=None, description="List of HTML tags to exclude from processing")
    excluded_selector: Optional[str] = Field(default=None, description="CSS selector to exclude from processing")
    remove_forms: Optional[bool] = Field(default=None, description="If True, remove all <form> elements from the HTML")
    prettiify: Optional[bool] = Field(default=None, description="If True, apply fast_format_html to produce prettified HTML output")
    parser_type: Optional[str] = Field(default=None, description="Type of parser to use for HTML parsing, default is lxml")
    wait_until: Optional[str] = Field(default=None, description="The condition to wait for when navigating, e.g. domcontentloaded")
    page_timeout: Optional[int] = Field(default=None, description="Timeout in ms for page operations like navigation")
    wait_for: Optional[str] = Field(default=None, description="A CSS selector or JS condition to wait for before extracting content")
    wait_for_timeout: Optional[int] = Field(default=None, description="Specific timeout in ms for the wait_for condition")
    delay_before_return_html: Optional[float] = Field(default=None, description="Delay in seconds before retrieving final HTML")
    scan_full_page: Optional[bool] = Field(default=None, description="If True, scroll through the entire page to load all content")
    scroll_delay: Optional[float] = Field(default=None, description="Delay in seconds between scroll steps if scan_full_page is True")
    process_iframes: Optional[bool] = Field(default=None, description="If True, attempts to process and inline iframe content")
    remove_overlay_elements: Optional[bool] = Field(default=None, description="If True, remove overlays/popups before extracting HTML")
    simulate_user: Optional[bool] = Field(default=None, description="If True, simulate user interactions for anti-bot measures")
    screenshot: Optional[bool] = Field(default=None, description="Whether to take a screenshot after crawling")
    screenshot_wait_for: Optional[float] = Field(default=None, description="Additional wait time before taking a screenshot")
    pdf: Optional[bool] = Field(default=None, description="Whether to generate a PDF of the page")
    exclude_external_images: Optional[bool] = Field(default=None, description="If True, exclude all external images from processing")
    exclude_all_images: Optional[bool] = Field(default=None, description="If True, exclude all images from processing")
    table_score_threshold: Optional[int] = Field(default=None, description="Minimum score threshold for processing a table")
    cache_mode: Optional[str] = Field(default=None, description="Defines how caching is handled: enabled, bypass, disabled, read_only, write_only")
    exclude_external_links: Optional[bool] = Field(default=None, description="If True, exclude all external links from the results")
    exclude_social_media_links: Optional[bool] = Field(default=None, description="If True, exclude links pointing to social media domains")
    exclude_domains: Optional[List[str]] = Field(default=None, description="List of specific domains to exclude from results")
    verbose: Optional[bool] = Field(default=None, description="Enable verbose logging")
    js_code: Optional[Union[str, List[str]]] = Field(default=None, description="JavaScript code/snippets to run on the page")
    wait_for_images: Optional[bool] = Field(default=None, description="If True, wait for images to load before extracting content")
    ignore_body_visibility: Optional[bool] = Field(default=None, description="If True, ignore whether the body is visible before proceeding")
    max_scroll_steps: Optional[int] = Field(default=None, description="Maximum number of scroll steps to perform during full page scan")
    override_navigator: Optional[bool] = Field(default=None, description="If True, overrides navigator properties for more human-like behavior")
    magic: Optional[bool] = Field(default=None, description="If True, attempts automatic handling of overlays/popups")
    adjust_viewport_to_content: Optional[bool] = Field(default=None, description="If True, adjust viewport according to the page content dimensions")
    browser_config: Optional[Dict] = Field(default_factory=dict, description="Browser configuration")
    crawler_config: Optional[Dict] = Field(default_factory=dict, description="Crawler configuration")


class Crawl4AICrawlTool(BaseTool):
    """LangChain tool for Crawl4AI synchronous crawling."""
    
    name: str = "crawl4ai_crawl"
    description: str = "Crawl web pages synchronously and return structured content as markdown"
    args_schema: Optional[type] = Crawl4AICrawlInput
    __metadata__ = {"source": "connector.crawl4ai"}
    
    def __init__(self):
        super().__init__()
    
    def get_config(self):
        """Get the Crawl4AI config for this tool"""
        if not hasattr(self, '_config'):
            self._config = Crawl4AIConfig()
        return self._config
    
    def _run(self, *args, **kwargs) -> str:
        """Synchronous run method - not implemented for async tool."""
        raise NotImplementedError("This tool only supports async execution")
    
    async def _arun(self, 
                   urls: List[str], 
                   word_count_threshold: Optional[int] = None,
                   only_text: Optional[bool] = None,
                   css_selector: Optional[str] = None,
                   target_elements: Optional[List[str]] = None,
                   excluded_tags: Optional[List[str]] = None,
                   excluded_selector: Optional[str] = None,
                   remove_forms: Optional[bool] = None,
                   prettiify: Optional[bool] = None,
                   parser_type: Optional[str] = None,
                   wait_until: Optional[str] = None,
                   page_timeout: Optional[int] = None,
                   wait_for: Optional[str] = None,
                   wait_for_timeout: Optional[int] = None,
                   delay_before_return_html: Optional[float] = None,
                   scan_full_page: Optional[bool] = None,
                   scroll_delay: Optional[float] = None,
                   process_iframes: Optional[bool] = None,
                   remove_overlay_elements: Optional[bool] = None,
                   simulate_user: Optional[bool] = None,
                   screenshot: Optional[bool] = None,
                   screenshot_wait_for: Optional[float] = None,
                   pdf: Optional[bool] = None,
                   exclude_external_images: Optional[bool] = None,
                   exclude_all_images: Optional[bool] = None,
                   table_score_threshold: Optional[int] = None,
                   cache_mode: Optional[str] = None,
                   exclude_external_links: Optional[bool] = None,
                   exclude_social_media_links: Optional[bool] = None,
                   exclude_domains: Optional[List[str]] = None,
                   verbose: Optional[bool] = None,
                   js_code: Optional[Union[str, List[str]]] = None,
                   wait_for_images: Optional[bool] = None,
                   ignore_body_visibility: Optional[bool] = None,
                   max_scroll_steps: Optional[int] = None,
                   override_navigator: Optional[bool] = None,
                   magic: Optional[bool] = None,
                   adjust_viewport_to_content: Optional[bool] = None,
                   browser_config: Optional[Dict] = None,
                   crawler_config: Optional[Dict] = None) -> str:
        """Asynchronously crawl web pages."""
        try:
            config = self.get_config()
            async with Crawl4AIClient(config) as client:
                # Create crawler_config from default values, overriding with config values, then with explicit parameters
                final_crawler_config = {}
                
                # Apply default config values
                final_crawler_config.update({
                    "word_count_threshold": config.word_count_threshold,
                    "only_text": config.only_text,
                    "css_selector": config.css_selector,
                    "target_elements": config.target_elements,
                    "excluded_tags": config.excluded_tags,
                    "excluded_selector": config.excluded_selector,
                    "remove_forms": config.remove_forms,
                    "prettiify": config.prettiify,
                    "parser_type": config.parser_type,
                    "wait_until": config.wait_until,
                    "page_timeout": config.page_timeout,
                    "wait_for": config.wait_for,
                    "wait_for_timeout": config.wait_for_timeout,
                    "delay_before_return_html": config.delay_before_return_html,
                    "scan_full_page": config.scan_full_page,
                    "scroll_delay": config.scroll_delay,
                    "process_iframes": config.process_iframes,
                    "remove_overlay_elements": config.remove_overlay_elements,
                    "simulate_user": config.simulate_user,
                    "screenshot": config.screenshot,
                    "screenshot_wait_for": config.screenshot_wait_for,
                    "pdf": config.pdf,
                    "exclude_external_images": config.exclude_external_images,
                    "exclude_all_images": config.exclude_all_images,
                    "table_score_threshold": config.table_score_threshold,
                    "cache_mode": config.cache_mode,
                    "exclude_external_links": config.exclude_external_links,
                    "exclude_social_media_links": config.exclude_social_media_links,
                    "exclude_domains": config.exclude_domains,
                    "verbose": config.verbose,
                    "js_code": config.js_code,
                    "wait_for_images": config.wait_for_images,
                    "ignore_body_visibility": config.ignore_body_visibility,
                    "max_scroll_steps": config.max_scroll_steps,
                    "override_navigator": config.override_navigator,
                    "magic": config.magic,
                    "adjust_viewport_to_content": config.adjust_viewport_to_content
                })
                
                # Override with explicitly passed parameters
                if word_count_threshold is not None:
                    final_crawler_config["word_count_threshold"] = word_count_threshold
                if only_text is not None:
                    final_crawler_config["only_text"] = only_text
                if css_selector is not None:
                    final_crawler_config["css_selector"] = css_selector
                if target_elements is not None:
                    final_crawler_config["target_elements"] = target_elements
                if excluded_tags is not None:
                    final_crawler_config["excluded_tags"] = excluded_tags
                if excluded_selector is not None:
                    final_crawler_config["excluded_selector"] = excluded_selector
                if remove_forms is not None:
                    final_crawler_config["remove_forms"] = remove_forms
                if prettiify is not None:
                    final_crawler_config["prettiify"] = prettiify
                if parser_type is not None:
                    final_crawler_config["parser_type"] = parser_type
                if wait_until is not None:
                    final_crawler_config["wait_until"] = wait_until
                if page_timeout is not None:
                    final_crawler_config["page_timeout"] = page_timeout
                if wait_for is not None:
                    final_crawler_config["wait_for"] = wait_for
                if wait_for_timeout is not None:
                    final_crawler_config["wait_for_timeout"] = wait_for_timeout
                if delay_before_return_html is not None:
                    final_crawler_config["delay_before_return_html"] = delay_before_return_html
                if scan_full_page is not None:
                    final_crawler_config["scan_full_page"] = scan_full_page
                if scroll_delay is not None:
                    final_crawler_config["scroll_delay"] = scroll_delay
                if process_iframes is not None:
                    final_crawler_config["process_iframes"] = process_iframes
                if remove_overlay_elements is not None:
                    final_crawler_config["remove_overlay_elements"] = remove_overlay_elements
                if simulate_user is not None:
                    final_crawler_config["simulate_user"] = simulate_user
                if screenshot is not None:
                    final_crawler_config["screenshot"] = screenshot
                if screenshot_wait_for is not None:
                    final_crawler_config["screenshot_wait_for"] = screenshot_wait_for
                if pdf is not None:
                    final_crawler_config["pdf"] = pdf
                if exclude_external_images is not None:
                    final_crawler_config["exclude_external_images"] = exclude_external_images
                if exclude_all_images is not None:
                    final_crawler_config["exclude_all_images"] = exclude_all_images
                if table_score_threshold is not None:
                    final_crawler_config["table_score_threshold"] = table_score_threshold
                if cache_mode is not None:
                    final_crawler_config["cache_mode"] = cache_mode
                if exclude_external_links is not None:
                    final_crawler_config["exclude_external_links"] = exclude_external_links
                if exclude_social_media_links is not None:
                    final_crawler_config["exclude_social_media_links"] = exclude_social_media_links
                if exclude_domains is not None:
                    final_crawler_config["exclude_domains"] = exclude_domains
                if verbose is not None:
                    final_crawler_config["verbose"] = verbose
                if js_code is not None:
                    final_crawler_config["js_code"] = js_code
                if wait_for_images is not None:
                    final_crawler_config["wait_for_images"] = wait_for_images
                if ignore_body_visibility is not None:
                    final_crawler_config["ignore_body_visibility"] = ignore_body_visibility
                if max_scroll_steps is not None:
                    final_crawler_config["max_scroll_steps"] = max_scroll_steps
                if override_navigator is not None:
                    final_crawler_config["override_navigator"] = override_navigator
                if magic is not None:
                    final_crawler_config["magic"] = magic
                if adjust_viewport_to_content is not None:
                    final_crawler_config["adjust_viewport_to_content"] = adjust_viewport_to_content

                # If crawler_config was explicitly passed, merge it with our defaults/overrides
                if crawler_config:
                    final_crawler_config.update(crawler_config)
                
                result = await client.crawl(
                    urls=urls,
                    browser_config=browser_config or {},
                    crawler_config=final_crawler_config
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error crawling URLs: {str(e)}"


class Crawl4AIStreamInput(BaseModel):
    """Input for Crawl4AI stream tool."""
    
    urls: List[str] = Field(..., description="List of URLs to crawl")
    word_count_threshold: Optional[int] = Field(default=None, description="Minimum word count threshold before processing content")
    only_text: Optional[bool] = Field(default=None, description="If True, attempt to extract text-only content")
    css_selector: Optional[str] = Field(default=None, description="CSS selector to extract a specific portion of the page")
    target_elements: Optional[List[str]] = Field(default=None, description="List of CSS selectors for specific elements for Markdown generation")
    excluded_tags: Optional[List[str]] = Field(default=None, description="List of HTML tags to exclude from processing")
    excluded_selector: Optional[str] = Field(default=None, description="CSS selector to exclude from processing")
    remove_forms: Optional[bool] = Field(default=None, description="If True, remove all <form> elements from the HTML")
    prettiify: Optional[bool] = Field(default=None, description="If True, apply fast_format_html to produce prettified HTML output")
    parser_type: Optional[str] = Field(default=None, description="Type of parser to use for HTML parsing, default is lxml")
    wait_until: Optional[str] = Field(default=None, description="The condition to wait for when navigating, e.g. domcontentloaded")
    page_timeout: Optional[int] = Field(default=None, description="Timeout in ms for page operations like navigation")
    wait_for: Optional[str] = Field(default=None, description="A CSS selector or JS condition to wait for before extracting content")
    wait_for_timeout: Optional[int] = Field(default=None, description="Specific timeout in ms for the wait_for condition")
    delay_before_return_html: Optional[float] = Field(default=None, description="Delay in seconds before retrieving final HTML")
    scan_full_page: Optional[bool] = Field(default=None, description="If True, scroll through the entire page to load all content")
    scroll_delay: Optional[float] = Field(default=None, description="Delay in seconds between scroll steps if scan_full_page is True")
    process_iframes: Optional[bool] = Field(default=None, description="If True, attempts to process and inline iframe content")
    remove_overlay_elements: Optional[bool] = Field(default=None, description="If True, remove overlays/popups before extracting HTML")
    simulate_user: Optional[bool] = Field(default=None, description="If True, simulate user interactions for anti-bot measures")
    screenshot: Optional[bool] = Field(default=None, description="Whether to take a screenshot after crawling")
    screenshot_wait_for: Optional[float] = Field(default=None, description="Additional wait time before taking a screenshot")
    pdf: Optional[bool] = Field(default=None, description="Whether to generate a PDF of the page")
    exclude_external_images: Optional[bool] = Field(default=None, description="If True, exclude all external images from processing")
    exclude_all_images: Optional[bool] = Field(default=None, description="If True, exclude all images from processing")
    table_score_threshold: Optional[int] = Field(default=None, description="Minimum score threshold for processing a table")
    cache_mode: Optional[str] = Field(default=None, description="Defines how caching is handled: enabled, bypass, disabled, read_only, write_only")
    exclude_external_links: Optional[bool] = Field(default=None, description="If True, exclude all external links from the results")
    exclude_social_media_links: Optional[bool] = Field(default=None, description="If True, exclude links pointing to social media domains")
    exclude_domains: Optional[List[str]] = Field(default=None, description="List of specific domains to exclude from results")
    verbose: Optional[bool] = Field(default=None, description="Enable verbose logging")
    js_code: Optional[Union[str, List[str]]] = Field(default=None, description="JavaScript code/snippets to run on the page")
    wait_for_images: Optional[bool] = Field(default=None, description="If True, wait for images to load before extracting content")
    ignore_body_visibility: Optional[bool] = Field(default=None, description="If True, ignore whether the body is visible before proceeding")
    max_scroll_steps: Optional[int] = Field(default=None, description="Maximum number of scroll steps to perform during full page scan")
    override_navigator: Optional[bool] = Field(default=None, description="If True, overrides navigator properties for more human-like behavior")
    magic: Optional[bool] = Field(default=None, description="If True, attempts automatic handling of overlays/popups")
    adjust_viewport_to_content: Optional[bool] = Field(default=None, description="If True, adjust viewport according to the page content dimensions")
    browser_config: Optional[Dict] = Field(default_factory=dict, description="Browser configuration")
    crawler_config: Optional[Dict] = Field(default_factory=dict, description="Crawler configuration")


class Crawl4AIStreamTool(BaseTool):
    """LangChain tool for Crawl4AI streaming crawling."""
    
    name: str = "crawl4ai_stream"
    description: str = "Crawl web pages with streaming and return structured content as markdown"
    args_schema: Optional[type] = Crawl4AIStreamInput
    __metadata__ = {"source": "connector.crawl4ai"}
    
    def __init__(self):
        super().__init__()
    
    def get_config(self):
        """Get the Crawl4AI config for this tool"""
        if not hasattr(self, '_config'):
            self._config = Crawl4AIConfig()
        return self._config
    
    def _run(self, *args, **kwargs) -> str:
        """Synchronous run method - not implemented for async tool."""
        raise NotImplementedError("This tool only supports async execution")
    
    async def _arun(self, 
                   urls: List[str], 
                   word_count_threshold: Optional[int] = None,
                   only_text: Optional[bool] = None,
                   css_selector: Optional[str] = None,
                   target_elements: Optional[List[str]] = None,
                   excluded_tags: Optional[List[str]] = None,
                   excluded_selector: Optional[str] = None,
                   remove_forms: Optional[bool] = None,
                   prettiify: Optional[bool] = None,
                   parser_type: Optional[str] = None,
                   wait_until: Optional[str] = None,
                   page_timeout: Optional[int] = None,
                   wait_for: Optional[str] = None,
                   wait_for_timeout: Optional[int] = None,
                   delay_before_return_html: Optional[float] = None,
                   scan_full_page: Optional[bool] = None,
                   scroll_delay: Optional[float] = None,
                   process_iframes: Optional[bool] = None,
                   remove_overlay_elements: Optional[bool] = None,
                   simulate_user: Optional[bool] = None,
                   screenshot: Optional[bool] = None,
                   screenshot_wait_for: Optional[float] = None,
                   pdf: Optional[bool] = None,
                   exclude_external_images: Optional[bool] = None,
                   exclude_all_images: Optional[bool] = None,
                   table_score_threshold: Optional[int] = None,
                   cache_mode: Optional[str] = None,
                   exclude_external_links: Optional[bool] = None,
                   exclude_social_media_links: Optional[bool] = None,
                   exclude_domains: Optional[List[str]] = None,
                   verbose: Optional[bool] = None,
                   js_code: Optional[Union[str, List[str]]] = None,
                   wait_for_images: Optional[bool] = None,
                   ignore_body_visibility: Optional[bool] = None,
                   max_scroll_steps: Optional[int] = None,
                   override_navigator: Optional[bool] = None,
                   magic: Optional[bool] = None,
                   adjust_viewport_to_content: Optional[bool] = None,
                   browser_config: Optional[Dict] = None,
                   crawler_config: Optional[Dict] = None) -> str:
        """Asynchronously crawl web pages with streaming."""
        try:
            results = []
            config = self.get_config()
            async with Crawl4AIClient(config) as client:
                # Create crawler_config from default values, overriding with config values, then with explicit parameters
                final_crawler_config = {}
                
                # Apply default config values
                final_crawler_config.update({
                    "word_count_threshold": config.word_count_threshold,
                    "only_text": config.only_text,
                    "css_selector": config.css_selector,
                    "target_elements": config.target_elements,
                    "excluded_tags": config.excluded_tags,
                    "excluded_selector": config.excluded_selector,
                    "remove_forms": config.remove_forms,
                    "prettiify": config.prettiify,
                    "parser_type": config.parser_type,
                    "wait_until": config.wait_until,
                    "page_timeout": config.page_timeout,
                    "wait_for": config.wait_for,
                    "wait_for_timeout": config.wait_for_timeout,
                    "delay_before_return_html": config.delay_before_return_html,
                    "scan_full_page": config.scan_full_page,
                    "scroll_delay": config.scroll_delay,
                    "process_iframes": config.process_iframes,
                    "remove_overlay_elements": config.remove_overlay_elements,
                    "simulate_user": config.simulate_user,
                    "screenshot": config.screenshot,
                    "screenshot_wait_for": config.screenshot_wait_for,
                    "pdf": config.pdf,
                    "exclude_external_images": config.exclude_external_images,
                    "exclude_all_images": config.exclude_all_images,
                    "table_score_threshold": config.table_score_threshold,
                    "cache_mode": config.cache_mode,
                    "exclude_external_links": config.exclude_external_links,
                    "exclude_social_media_links": config.exclude_social_media_links,
                    "exclude_domains": config.exclude_domains,
                    "verbose": config.verbose,
                    "js_code": config.js_code,
                    "wait_for_images": config.wait_for_images,
                    "ignore_body_visibility": config.ignore_body_visibility,
                    "max_scroll_steps": config.max_scroll_steps,
                    "override_navigator": config.override_navigator,
                    "magic": config.magic,
                    "adjust_viewport_to_content": config.adjust_viewport_to_content
                })
                
                # Override with explicitly passed parameters
                if word_count_threshold is not None:
                    final_crawler_config["word_count_threshold"] = word_count_threshold
                if only_text is not None:
                    final_crawler_config["only_text"] = only_text
                if css_selector is not None:
                    final_crawler_config["css_selector"] = css_selector
                if target_elements is not None:
                    final_crawler_config["target_elements"] = target_elements
                if excluded_tags is not None:
                    final_crawler_config["excluded_tags"] = excluded_tags
                if excluded_selector is not None:
                    final_crawler_config["excluded_selector"] = excluded_selector
                if remove_forms is not None:
                    final_crawler_config["remove_forms"] = remove_forms
                if prettiify is not None:
                    final_crawler_config["prettiify"] = prettiify
                if parser_type is not None:
                    final_crawler_config["parser_type"] = parser_type
                if wait_until is not None:
                    final_crawler_config["wait_until"] = wait_until
                if page_timeout is not None:
                    final_crawler_config["page_timeout"] = page_timeout
                if wait_for is not None:
                    final_crawler_config["wait_for"] = wait_for
                if wait_for_timeout is not None:
                    final_crawler_config["wait_for_timeout"] = wait_for_timeout
                if delay_before_return_html is not None:
                    final_crawler_config["delay_before_return_html"] = delay_before_return_html
                if scan_full_page is not None:
                    final_crawler_config["scan_full_page"] = scan_full_page
                if scroll_delay is not None:
                    final_crawler_config["scroll_delay"] = scroll_delay
                if process_iframes is not None:
                    final_crawler_config["process_iframes"] = process_iframes
                if remove_overlay_elements is not None:
                    final_crawler_config["remove_overlay_elements"] = remove_overlay_elements
                if simulate_user is not None:
                    final_crawler_config["simulate_user"] = simulate_user
                if screenshot is not None:
                    final_crawler_config["screenshot"] = screenshot
                if screenshot_wait_for is not None:
                    final_crawler_config["screenshot_wait_for"] = screenshot_wait_for
                if pdf is not None:
                    final_crawler_config["pdf"] = pdf
                if exclude_external_images is not None:
                    final_crawler_config["exclude_external_images"] = exclude_external_images
                if exclude_all_images is not None:
                    final_crawler_config["exclude_all_images"] = exclude_all_images
                if table_score_threshold is not None:
                    final_crawler_config["table_score_threshold"] = table_score_threshold
                if cache_mode is not None:
                    final_crawler_config["cache_mode"] = cache_mode
                if exclude_external_links is not None:
                    final_crawler_config["exclude_external_links"] = exclude_external_links
                if exclude_social_media_links is not None:
                    final_crawler_config["exclude_social_media_links"] = exclude_social_media_links
                if exclude_domains is not None:
                    final_crawler_config["exclude_domains"] = exclude_domains
                if verbose is not None:
                    final_crawler_config["verbose"] = verbose
                if js_code is not None:
                    final_crawler_config["js_code"] = js_code
                if wait_for_images is not None:
                    final_crawler_config["wait_for_images"] = wait_for_images
                if ignore_body_visibility is not None:
                    final_crawler_config["ignore_body_visibility"] = ignore_body_visibility
                if max_scroll_steps is not None:
                    final_crawler_config["max_scroll_steps"] = max_scroll_steps
                if override_navigator is not None:
                    final_crawler_config["override_navigator"] = override_navigator
                if magic is not None:
                    final_crawler_config["magic"] = magic
                if adjust_viewport_to_content is not None:
                    final_crawler_config["adjust_viewport_to_content"] = adjust_viewport_to_content

                # If crawler_config was explicitly passed, merge it with our defaults/overrides
                if crawler_config:
                    final_crawler_config.update(crawler_config)
                
                async for result in client.crawl_stream(
                    urls=urls,
                    browser_config=browser_config or {},
                    crawler_config=final_crawler_config
                ):
                    # Stop when we receive completion marker
                    if result.get("status") == "completed":
                        break
                    results.append(result)
                
                return json.dumps(results, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error streaming crawl for URLs: {str(e)}"


