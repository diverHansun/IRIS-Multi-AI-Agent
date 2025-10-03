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
    
    # Configuration based on Crawl4AI SDK classes
    browser_config: Optional[Dict] = Field(default_factory=dict, description="Browser configuration parameters based on BrowserConfig class")
    crawler_config: Optional[Dict] = Field(default_factory=dict, description="Crawler configuration parameters based on CrawlerRunConfig class")
    http_config: Optional[Dict] = Field(default_factory=dict, description="HTTP configuration parameters based on HTTPCrawlerConfig class (reserved for future use)")
    geolocation_config: Optional[Dict] = Field(default_factory=dict, description="Geolocation configuration parameters based on GeolocationConfig class (reserved for future use)")
    proxy_config: Optional[Dict] = Field(default_factory=dict, description="Proxy configuration parameters based on ProxyConfig class (reserved for future use)")
    virtual_scroll_config: Optional[Dict] = Field(default_factory=dict, description="Virtual scroll configuration parameters based on VirtualScrollConfig class (reserved for future use)")
    link_preview_config: Optional[Dict] = Field(default_factory=dict, description="Link preview configuration parameters based on LinkPreviewConfig class (reserved for future use)")
    llm_config: Optional[Dict] = Field(default_factory=dict, description="LLM configuration parameters based on LLMConfig class (reserved for future use)")
    seeding_config: Optional[Dict] = Field(default_factory=dict, description="Seeding configuration parameters based on SeedingConfig class (reserved for future use)")


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
        # Get crawler config from the main config object (this comes from config file)
        base_crawler_config = getattr(config, 'crawler_config', {})

        # Return a copy to avoid modifying the original config
        return base_crawler_config.copy() if base_crawler_config else {}

    def _apply_parameter_overrides(self, crawler_config, **kwargs):
        """Apply explicit parameter overrides to crawler config"""
        # Apply any additional parameters from kwargs that are not None
        # This allows for parameter overrides beyond the main config dictionaries
        for key, value in kwargs.items():
            if value is not None:
                crawler_config[key] = value
    
    def _run(self, *args, **kwargs) -> str:
        """Synchronous run method - not implemented for async tool."""
        raise NotImplementedError("This tool only supports async execution")
    
    async def _arun(self, 
                   urls: List[str], 
                   browser_config: Optional[Dict] = None,
                   crawler_config: Optional[Dict] = None,
                   http_config: Optional[Dict] = None,
                   geolocation_config: Optional[Dict] = None,
                   proxy_config: Optional[Dict] = None,
                   virtual_scroll_config: Optional[Dict] = None,
                   link_preview_config: Optional[Dict] = None,
                   llm_config: Optional[Dict] = None,
                   seeding_config: Optional[Dict] = None) -> str:
        """Asynchronously crawl web pages."""
        try:
            config = self.get_config()
            async with Crawl4AIClient(config) as client:
                # Build base crawler config from the configuration (loaded from config.json)
                final_crawler_config = self._build_base_crawler_config(config)
                
                # If crawler_config was explicitly passed as a parameter (not None), 
                # merge it with the base config. If None, keep using base config from config.json
                if crawler_config is not None:
                    final_crawler_config.update(crawler_config)
                
                # Determine browser_config to use - start with config file values, then override if parameter provided
                final_browser_config = getattr(config, 'browser_config', {}).copy() if hasattr(config, 'browser_config') else {}
                if browser_config is not None:
                    final_browser_config.update(browser_config)
                
                result = await client.crawl(
                    urls=urls,
                    browser_config=final_browser_config,
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



