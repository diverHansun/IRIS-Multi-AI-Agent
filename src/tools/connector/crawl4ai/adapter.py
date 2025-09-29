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
    # LLM-focused parameters
    content_filter_type: Optional[str] = Field(default=None, description="Content filter type: pruning, bm25, or none")
    pruning_threshold: Optional[float] = Field(default=None, description="Content retention threshold for pruning filter (0-1)")
    pruning_threshold_type: Optional[str] = Field(default=None, description="Threshold type: fixed or dynamic")
    min_word_threshold: Optional[int] = Field(default=None, description="Minimum word count for content blocks")
    bm25_threshold: Optional[float] = Field(default=None, description="BM25 relevance threshold")
    user_query: Optional[str] = Field(default=None, description="Query for BM25 content filtering")
    max_token_length: Optional[int] = Field(default=None, description="Maximum token length for LLM processing")
    prefer_fit_markdown: Optional[bool] = Field(default=None, description="Prefer fit_markdown over raw_markdown")
    extract_main_content: Optional[bool] = Field(default=None, description="Extract only main content area")
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

    def _build_base_crawler_config(self, config):
        """Build base crawler config from configuration"""
        return {
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
            "adjust_viewport_to_content": config.adjust_viewport_to_content,
            # LLM-focused parameters
            "content_filter_type": getattr(config, 'content_filter_type', None),
            "pruning_threshold": getattr(config, 'pruning_threshold', None),
            "pruning_threshold_type": getattr(config, 'pruning_threshold_type', None),
            "min_word_threshold": getattr(config, 'min_word_threshold', None),
            "bm25_threshold": getattr(config, 'bm25_threshold', None),
            "user_query": getattr(config, 'user_query', None),
            "max_token_length": getattr(config, 'max_token_length', None),
            "prefer_fit_markdown": getattr(config, 'prefer_fit_markdown', None),
            "extract_main_content": getattr(config, 'extract_main_content', None)
        }

    def _apply_parameter_overrides(self, crawler_config, **kwargs):
        """Apply explicit parameter overrides to crawler config"""
        override_mapping = {
            'word_count_threshold': 'word_count_threshold',
            'only_text': 'only_text',
            'css_selector': 'css_selector',
            'target_elements': 'target_elements',
            'excluded_tags': 'excluded_tags',
            'excluded_selector': 'excluded_selector',
            'remove_forms': 'remove_forms',
            'prettiify': 'prettiify',
            'parser_type': 'parser_type',
            'wait_until': 'wait_until',
            'page_timeout': 'page_timeout',
            'wait_for': 'wait_for',
            'wait_for_timeout': 'wait_for_timeout',
            'delay_before_return_html': 'delay_before_return_html',
            'scan_full_page': 'scan_full_page',
            'scroll_delay': 'scroll_delay',
            'process_iframes': 'process_iframes',
            'remove_overlay_elements': 'remove_overlay_elements',
            'simulate_user': 'simulate_user',
            'screenshot': 'screenshot',
            'screenshot_wait_for': 'screenshot_wait_for',
            'pdf': 'pdf',
            'exclude_external_images': 'exclude_external_images',
            'exclude_all_images': 'exclude_all_images',
            'table_score_threshold': 'table_score_threshold',
            'cache_mode': 'cache_mode',
            'exclude_external_links': 'exclude_external_links',
            'exclude_social_media_links': 'exclude_social_media_links',
            'exclude_domains': 'exclude_domains',
            'verbose': 'verbose',
            'js_code': 'js_code',
            'wait_for_images': 'wait_for_images',
            'ignore_body_visibility': 'ignore_body_visibility',
            'max_scroll_steps': 'max_scroll_steps',
            'override_navigator': 'override_navigator',
            'magic': 'magic',
            'adjust_viewport_to_content': 'adjust_viewport_to_content',
            # LLM-focused parameters
            'content_filter_type': 'content_filter_type',
            'pruning_threshold': 'pruning_threshold',
            'pruning_threshold_type': 'pruning_threshold_type',
            'min_word_threshold': 'min_word_threshold',
            'bm25_threshold': 'bm25_threshold',
            'user_query': 'user_query',
            'max_token_length': 'max_token_length',
            'prefer_fit_markdown': 'prefer_fit_markdown',
            'extract_main_content': 'extract_main_content'
        }

        for param_name, config_key in override_mapping.items():
            if kwargs.get(param_name) is not None:
                crawler_config[config_key] = kwargs[param_name]
    
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
                   # LLM-focused parameters
                   content_filter_type: Optional[str] = None,
                   pruning_threshold: Optional[float] = None,
                   pruning_threshold_type: Optional[str] = None,
                   min_word_threshold: Optional[int] = None,
                   bm25_threshold: Optional[float] = None,
                   user_query: Optional[str] = None,
                   max_token_length: Optional[int] = None,
                   prefer_fit_markdown: Optional[bool] = None,
                   extract_main_content: Optional[bool] = None,
                   browser_config: Optional[Dict] = None,
                   crawler_config: Optional[Dict] = None) -> str:
        """Asynchronously crawl web pages."""
        try:
            config = self.get_config()
            async with Crawl4AIClient(config) as client:
                # Build base crawler config and apply parameter overrides
                final_crawler_config = self._build_base_crawler_config(config)
                # Collect all parameters in a kwargs dict
                kwargs = locals().copy()
                kwargs.pop('self')
                kwargs.pop('config')
                kwargs.pop('client', None)
                kwargs.pop('final_crawler_config', None)
                self._apply_parameter_overrides(final_crawler_config, **kwargs)

                # If crawler_config was explicitly passed, merge it with our defaults/overrides
                if kwargs.get('crawler_config'):
                    final_crawler_config.update(kwargs['crawler_config'])
                
                result = await client.crawl(
                    urls=kwargs['urls'],
                    browser_config=kwargs.get('browser_config', {}),
                    crawler_config=final_crawler_config
                )
                
                # Check the configuration to determine return format
                config = self.get_config()
                return_format = getattr(config, 'return_format', 'markdown')  # default to markdown
                
                # If configured to return JSON, return the raw result
                if return_format == 'json':
                    return json.dumps(result, ensure_ascii=False, indent=2)
                
                # Otherwise, extract markdown content from the result
                markdown_content = ""
                
                # The result from the HTTP API might have a specific structure
                # Based on typical Crawl4AI API response structure
                if isinstance(result, dict):
                    if 'results' in result:
                        # Process each result in the results array
                        for crawl_result in result['results']:
                            # Look for markdown content in the crawl result
                            if isinstance(crawl_result, dict):
                                # Check if direct markdown field exists
                                if 'markdown' in crawl_result:
                                    if isinstance(crawl_result['markdown'], str):
                                        markdown_content += crawl_result['markdown']
                                    elif isinstance(crawl_result['markdown'], dict):
                                        # Try to access markdown fields as per Crawl4AI documentation
                                        markdown_obj = crawl_result['markdown']
                                        # Check preference for fit_markdown
                                        prefer_fit = final_crawler_config.get('prefer_fit_markdown', False)

                                        if prefer_fit and 'fit_markdown' in markdown_obj and markdown_obj['fit_markdown']:
                                            markdown_content += markdown_obj['fit_markdown']
                                        elif 'fit_markdown' in markdown_obj and markdown_obj['fit_markdown']:
                                            markdown_content += markdown_obj['fit_markdown']
                                        elif 'raw_markdown' in markdown_obj and markdown_obj['raw_markdown']:
                                            markdown_content += markdown_obj['raw_markdown']
                                        elif 'markdown_with_citations' in markdown_obj and markdown_obj['markdown_with_citations']:
                                            markdown_content += markdown_obj['markdown_with_citations']
                                        else:
                                            # If we can't find expected markdown fields, fall back to full object
                                            markdown_content += json.dumps(crawl_result['markdown'], ensure_ascii=False, indent=2)
                                elif 'content' in crawl_result:
                                    # Fallback: use content field if available
                                    markdown_content += crawl_result['content']
                                else:
                                    # If no markdown/content found, include the whole result as JSON
                                    markdown_content += json.dumps(crawl_result, ensure_ascii=False, indent=2)
                            else:
                                # If crawl_result is not a dict, convert to string
                                markdown_content += str(crawl_result)
                            
                            # Add separator between results if there are multiple URLs
                            markdown_content += "\n\n---\n\n"
                    else:
                        # If no 'results' field, treat the entire result as one response
                        if 'markdown' in result:
                            if isinstance(result['markdown'], str):
                                markdown_content = result['markdown']
                            elif isinstance(result['markdown'], dict):
                                markdown_obj = result['markdown']
                                if 'fit_markdown' in markdown_obj and markdown_obj['fit_markdown']:
                                    markdown_content = markdown_obj['fit_markdown']
                                elif 'raw_markdown' in markdown_obj and markdown_obj['raw_markdown']:
                                    markdown_content = markdown_obj['raw_markdown']
                                elif 'markdown_with_citations' in markdown_obj and markdown_obj['markdown_with_citations']:
                                    markdown_content = markdown_obj['markdown_with_citations']
                                else:
                                    markdown_content = json.dumps(result['markdown'], ensure_ascii=False, indent=2)
                        elif 'content' in result:
                            markdown_content = result['content']
                        else:
                            # Fallback to return JSON if no markdown found
                            markdown_content = json.dumps(result, ensure_ascii=False, indent=2)
                else:
                    # If result is not a dict, convert to string
                    markdown_content = str(result)
                
                # Remove the last separator if it exists
                if markdown_content.endswith("\n\n---\n\n"):
                    markdown_content = markdown_content[:-8]
                
                return markdown_content
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
    # LLM-focused parameters
    content_filter_type: Optional[str] = Field(default=None, description="Content filter type: pruning, bm25, or none")
    pruning_threshold: Optional[float] = Field(default=None, description="Content retention threshold for pruning filter (0-1)")
    pruning_threshold_type: Optional[str] = Field(default=None, description="Threshold type: fixed or dynamic")
    min_word_threshold: Optional[int] = Field(default=None, description="Minimum word count for content blocks")
    bm25_threshold: Optional[float] = Field(default=None, description="BM25 relevance threshold")
    user_query: Optional[str] = Field(default=None, description="Query for BM25 content filtering")
    max_token_length: Optional[int] = Field(default=None, description="Maximum token length for LLM processing")
    prefer_fit_markdown: Optional[bool] = Field(default=None, description="Prefer fit_markdown over raw_markdown")
    extract_main_content: Optional[bool] = Field(default=None, description="Extract only main content area")
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

    def _build_base_crawler_config(self, config):
        """Build base crawler config from configuration"""
        return {
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
            "adjust_viewport_to_content": config.adjust_viewport_to_content,
            # LLM-focused parameters
            "content_filter_type": getattr(config, 'content_filter_type', None),
            "pruning_threshold": getattr(config, 'pruning_threshold', None),
            "pruning_threshold_type": getattr(config, 'pruning_threshold_type', None),
            "min_word_threshold": getattr(config, 'min_word_threshold', None),
            "bm25_threshold": getattr(config, 'bm25_threshold', None),
            "user_query": getattr(config, 'user_query', None),
            "max_token_length": getattr(config, 'max_token_length', None),
            "prefer_fit_markdown": getattr(config, 'prefer_fit_markdown', None),
            "extract_main_content": getattr(config, 'extract_main_content', None)
        }

    def _apply_parameter_overrides(self, crawler_config, **kwargs):
        """Apply explicit parameter overrides to crawler config"""
        override_mapping = {
            'word_count_threshold': 'word_count_threshold',
            'only_text': 'only_text',
            'css_selector': 'css_selector',
            'target_elements': 'target_elements',
            'excluded_tags': 'excluded_tags',
            'excluded_selector': 'excluded_selector',
            'remove_forms': 'remove_forms',
            'prettiify': 'prettiify',
            'parser_type': 'parser_type',
            'wait_until': 'wait_until',
            'page_timeout': 'page_timeout',
            'wait_for': 'wait_for',
            'wait_for_timeout': 'wait_for_timeout',
            'delay_before_return_html': 'delay_before_return_html',
            'scan_full_page': 'scan_full_page',
            'scroll_delay': 'scroll_delay',
            'process_iframes': 'process_iframes',
            'remove_overlay_elements': 'remove_overlay_elements',
            'simulate_user': 'simulate_user',
            'screenshot': 'screenshot',
            'screenshot_wait_for': 'screenshot_wait_for',
            'pdf': 'pdf',
            'exclude_external_images': 'exclude_external_images',
            'exclude_all_images': 'exclude_all_images',
            'table_score_threshold': 'table_score_threshold',
            'cache_mode': 'cache_mode',
            'exclude_external_links': 'exclude_external_links',
            'exclude_social_media_links': 'exclude_social_media_links',
            'exclude_domains': 'exclude_domains',
            'verbose': 'verbose',
            'js_code': 'js_code',
            'wait_for_images': 'wait_for_images',
            'ignore_body_visibility': 'ignore_body_visibility',
            'max_scroll_steps': 'max_scroll_steps',
            'override_navigator': 'override_navigator',
            'magic': 'magic',
            'adjust_viewport_to_content': 'adjust_viewport_to_content',
            # LLM-focused parameters
            'content_filter_type': 'content_filter_type',
            'pruning_threshold': 'pruning_threshold',
            'pruning_threshold_type': 'pruning_threshold_type',
            'min_word_threshold': 'min_word_threshold',
            'bm25_threshold': 'bm25_threshold',
            'user_query': 'user_query',
            'max_token_length': 'max_token_length',
            'prefer_fit_markdown': 'prefer_fit_markdown',
            'extract_main_content': 'extract_main_content'
        }

        for param_name, config_key in override_mapping.items():
            if kwargs.get(param_name) is not None:
                crawler_config[config_key] = kwargs[param_name]
    
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
                   # LLM-focused parameters
                   content_filter_type: Optional[str] = None,
                   pruning_threshold: Optional[float] = None,
                   pruning_threshold_type: Optional[str] = None,
                   min_word_threshold: Optional[int] = None,
                   bm25_threshold: Optional[float] = None,
                   user_query: Optional[str] = None,
                   max_token_length: Optional[int] = None,
                   prefer_fit_markdown: Optional[bool] = None,
                   extract_main_content: Optional[bool] = None,
                   browser_config: Optional[Dict] = None,
                   crawler_config: Optional[Dict] = None) -> str:
        """Asynchronously crawl web pages with streaming."""
        try:
            results = []
            config = self.get_config()
            async with Crawl4AIClient(config) as client:
                # Build base crawler config and apply parameter overrides
                final_crawler_config = self._build_base_crawler_config(config)
                # Collect all parameters in a kwargs dict
                kwargs = locals().copy()
                kwargs.pop('self')
                kwargs.pop('config')
                kwargs.pop('client', None)
                kwargs.pop('final_crawler_config', None)
                kwargs.pop('results', None)
                self._apply_parameter_overrides(final_crawler_config, **kwargs)
                # If crawler_config was explicitly passed, merge it with our defaults/overrides
                if kwargs.get('crawler_config'):
                    final_crawler_config.update(kwargs['crawler_config'])
                
                results = []  # Maintain results list for potential JSON return
                markdown_content = ""
                async for result in client.crawl_stream(
                    urls=kwargs['urls'],
                    browser_config=kwargs.get('browser_config', {}),
                    crawler_config=final_crawler_config
                ):
                    # Stop when we receive completion marker
                    if result.get("status") == "completed":
                        break

                    # Check the configuration to determine return format
                    config = self.get_config()
                    return_format = getattr(config, 'return_format', 'markdown')  # default to markdown

                    # If configured to return JSON, add the raw result to the results list for JSON serialization
                    if return_format == 'json':
                        results.append(result)
                        continue

                    # Otherwise, extract markdown content from each streamed result
                    if isinstance(result, dict):
                        if 'markdown' in result:
                            if isinstance(result['markdown'], str):
                                markdown_content += result['markdown']
                            elif isinstance(result['markdown'], dict):
                                markdown_obj = result['markdown']
                                # Check preference for fit_markdown
                                prefer_fit = final_crawler_config.get('prefer_fit_markdown', False)

                                if prefer_fit and 'fit_markdown' in markdown_obj and markdown_obj['fit_markdown']:
                                    markdown_content += markdown_obj['fit_markdown']
                                elif 'fit_markdown' in markdown_obj and markdown_obj['fit_markdown']:
                                    markdown_content += markdown_obj['fit_markdown']
                                elif 'raw_markdown' in markdown_obj and markdown_obj['raw_markdown']:
                                    markdown_content += markdown_obj['raw_markdown']
                                elif 'markdown_with_citations' in markdown_obj and markdown_obj['markdown_with_citations']:
                                    markdown_content += markdown_obj['markdown_with_citations']
                                else:
                                    # If we can't find expected markdown fields, fall back to full object
                                    markdown_content += json.dumps(result['markdown'], ensure_ascii=False, indent=2)
                        elif 'content' in result:
                            # Fallback: use content field if available
                            markdown_content += result['content']
                        else:
                            # If no markdown/content found, include the whole result as JSON
                            markdown_content += json.dumps(result, ensure_ascii=False, indent=2)
                    else:
                        # If result is not a dict, convert to string
                        markdown_content += str(result)

                    # Add a separator between different chunks if needed
                    markdown_content += "\n\n---\n\n"

                    results.append(result)
                
                # Check the configuration to determine return format
                config = self.get_config()
                return_format = getattr(config, 'return_format', 'markdown')  # default to markdown

                # If configured to return JSON, return the collected JSON results
                if return_format == 'json':
                    return json.dumps(results, ensure_ascii=False, indent=2)

                # Remove the last separator if it exists
                if markdown_content.endswith("\n\n---\n\n"):
                    markdown_content = markdown_content[:-8]

                return markdown_content
        except Exception as e:
            return f"Error streaming crawl for URLs: {str(e)}"


