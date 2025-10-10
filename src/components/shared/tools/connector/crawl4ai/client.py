"""
HTTP client for Crawl4AI connector
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, AsyncGenerator
import httpx
from .config import Crawl4AIConfig
from .errors import Crawl4AIConnectorError, Crawl4AIHTTPError


class Crawl4AIClient:
    """HTTP client for Crawl4AI Docker service"""
    
    def __init__(self, config: Optional[Crawl4AIConfig] = None):
        self.config = config or Crawl4AIConfig()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        headers = {"Content-Type": "application/json"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=headers,
            timeout=self.config.timeout,
            trust_env=False  # Don't use environment proxy settings which may interfere with localhost
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a request with retry logic"""
        if not self._client:
            raise Crawl4AIConnectorError("Client not initialized. Use as async context manager.")
        
        last_exception = None
        
        for attempt in range(self.config.retry_attempts + 1):
            try:
                response = await self._client.request(method, endpoint, json=data)
                
                # Check if request was successful
                if response.status_code == 200:
                    return response.json()
                
                # Handle specific HTTP errors
                if response.status_code == 401:
                    raise Crawl4AIHTTPError("Authentication required", response.status_code)
                elif response.status_code == 400:
                    raise Crawl4AIHTTPError(f"Bad request: {response.text}", response.status_code)
                elif response.status_code == 429:
                    raise Crawl4AIHTTPError("Rate limit exceeded", response.status_code)
                elif response.status_code >= 500:
                    raise Crawl4AIHTTPError(f"Server error: {response.text}", response.status_code)
                else:
                    raise Crawl4AIHTTPError(f"Request failed: {response.text}", response.status_code)
                    
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exception = e
                if attempt < self.config.retry_attempts:
                    # Wait before retry with exponential backoff
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    raise Crawl4AIConnectorError(f"Request failed after {self.config.retry_attempts + 1} attempts: {str(e)}")
        
        # This should not be reached, but just in case
        raise last_exception or Crawl4AIConnectorError("Request failed")
    
    async def health_check(self) -> bool:
        """Check if Crawl4AI service is healthy"""
        try:
            result = await self._make_request("GET", "/health")
            return result.get("status") == "ok"
        except Exception:
            return False
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get the schema for available configurations"""
        return await self._make_request("GET", "/schema")
    
    async def crawl(self, urls: List[str], 
                   browser_config: Optional[Dict] = None,
                   crawler_config: Optional[Dict] = None) -> Dict[str, Any]:
        """Perform a synchronous crawl"""
        payload = {
            "urls": urls,
            "browser_config": browser_config or {},
            "crawler_config": crawler_config or {}
        }
        
        # Temporarily increase timeout for this request
        original_timeout = self._client.timeout if self._client else None
        if self._client:
            self._client.timeout = httpx.Timeout(self.config.timeout)
        
        try:
            result = await self._make_request("POST", "/crawl", payload)
            return result
        finally:
            if self._client and original_timeout:
                self._client.timeout = original_timeout
    
    async def crawl_stream(self, urls: List[str], 
                          browser_config: Optional[Dict] = None,
                          crawler_config: Optional[Dict] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Perform a streaming crawl"""
        payload = {
            "urls": urls,
            "browser_config": browser_config or {},
            "crawler_config": crawler_config or {}
        }
        
        # For streaming, we need to make the request directly without using _make_request
        if not self._client:
            raise Crawl4AIConnectorError("Client not initialized. Use as async context manager.")
        
        # Temporarily increase timeout for streaming request
        original_timeout = self._client.timeout
        self._client.timeout = httpx.Timeout(self.config.stream_timeout)
        
        try:
            async with self._client.stream("POST", "/crawl/stream", json=payload) as response:
                if response.status_code != 200:
                    if response.status_code == 401:
                        raise Crawl4AIHTTPError("Authentication required", response.status_code)
                    elif response.status_code == 400:
                        raise Crawl4AIHTTPError(f"Bad request: {await response.aread()}", response.status_code)
                    elif response.status_code == 429:
                        raise Crawl4AIHTTPError("Rate limit exceeded", response.status_code)
                    elif response.status_code >= 500:
                        raise Crawl4AIHTTPError(f"Server error: {await response.aread()}", response.status_code)
                    else:
                        raise Crawl4AIHTTPError(f"Request failed: {await response.aread()}", response.status_code)
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            yield data
                        except json.JSONDecodeError:
                            # Skip invalid JSON lines
                            continue
        finally:
            # Restore original timeout
            self._client.timeout = original_timeout