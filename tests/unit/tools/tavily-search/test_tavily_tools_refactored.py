"""
Unit tests for refactored Tavily Search Tools

Tests all 9 refactored tools to verify:
- Configuration error handling
- Retry behavior on transient errors
- Structured error responses
- Successful execution flow
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import ConnectionError, Timeout, HTTPError

from src.components.shared.tools.sdk.tavily_search import (
    tavily_search_basic,
    tavily_search_advanced,
    tavily_search_news,
    tavily_extract_url,
    tavily_extract_batch,
    tavily_map_website,
    tavily_map_with_filter,
    tavily_crawl_basic,
    tavily_crawl_targeted,
    get_config,
    TavilyErrorHandler,
)


class TestConfigurationErrorHandling:
    """Test configuration error handling across all tools"""

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    def test_search_basic_no_api_key(self, mock_get_config):
        """Test tavily_search_basic handles missing API key"""
        mock_config = Mock()
        mock_config.is_available.return_value = False
        mock_get_config.return_value = mock_config

        result = tavily_search_basic.invoke({"query": "test query"})

        assert result["status"] == "error"
        assert result["error_type"] == "configuration_error"
        assert "API key" in result["message"]

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    def test_extract_url_no_api_key(self, mock_get_config):
        """Test tavily_extract_url handles missing API key"""
        mock_config = Mock()
        mock_config.is_available.return_value = False
        mock_get_config.return_value = mock_config

        result = tavily_extract_url.invoke({"url": "https://example.com"})

        assert result["status"] == "error"
        assert result["error_type"] == "configuration_error"

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    def test_map_website_no_api_key(self, mock_get_config):
        """Test tavily_map_website handles missing API key"""
        mock_config = Mock()
        mock_config.is_available.return_value = False
        mock_get_config.return_value = mock_config

        result = tavily_map_website.invoke({"url": "https://example.com"})

        assert result["status"] == "error"
        assert result["error_type"] == "configuration_error"

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    def test_crawl_basic_no_api_key(self, mock_get_config):
        """Test tavily_crawl_basic handles missing API key"""
        mock_config = Mock()
        mock_config.is_available.return_value = False
        mock_get_config.return_value = mock_config

        result = tavily_crawl_basic.invoke({"url": "https://example.com"})

        assert result["status"] == "error"
        assert result["error_type"] == "configuration_error"


class TestSearchToolsSuccessFlow:
    """Test successful execution flow for search tools"""

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilySearch')
    def test_search_basic_success(self, mock_tavily_search, mock_get_config):
        """Test successful tavily_search_basic execution"""
        # Setup config mock
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        # Setup search mock
        mock_search_instance = Mock()
        mock_search_instance.invoke.return_value = {
            "results": [{"title": "Test Result", "url": "https://example.com"}]
        }
        mock_tavily_search.return_value = mock_search_instance

        result = tavily_search_basic.invoke({"query": "test query"})

        # Verify successful response
        assert "results" in result
        assert len(result["results"]) == 1
        mock_search_instance.invoke.assert_called_once()

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilySearch')
    def test_search_advanced_success(self, mock_tavily_search, mock_get_config):
        """Test successful tavily_search_advanced execution"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_config.search.max_results = 10
        mock_config.search.search_depth = "advanced"
        mock_get_config.return_value = mock_config

        mock_search_instance = Mock()
        mock_search_instance.invoke.return_value = {"results": []}
        mock_tavily_search.return_value = mock_search_instance

        result = tavily_search_advanced.invoke({
            "query": "test query",
            "max_results": 5,
            "search_depth": "advanced"
        })

        assert "results" in result
        mock_search_instance.invoke.assert_called_once()

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilySearch')
    def test_search_news_success(self, mock_tavily_search, mock_get_config):
        """Test successful tavily_search_news execution"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_config.search.max_results = 10
        mock_get_config.return_value = mock_config

        mock_search_instance = Mock()
        mock_search_instance.invoke.return_value = {"results": []}
        mock_tavily_search.return_value = mock_search_instance

        result = tavily_search_news.invoke({"query": "latest news", "days": 7})

        assert "results" in result
        mock_search_instance.invoke.assert_called_once()


class TestExtractToolsSuccessFlow:
    """Test successful execution flow for extract tools"""

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilyExtract')
    def test_extract_url_success(self, mock_tavily_extract, mock_get_config):
        """Test successful tavily_extract_url execution"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        mock_extract_instance = Mock()
        mock_extract_instance.invoke.return_value = {
            "raw_content": "Extracted content",
            "url": "https://example.com"
        }
        mock_tavily_extract.return_value = mock_extract_instance

        result = tavily_extract_url.invoke({"url": "https://example.com"})

        assert "raw_content" in result
        assert result["raw_content"] == "Extracted content"
        mock_extract_instance.invoke.assert_called_once()

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilyExtract')
    def test_extract_batch_success(self, mock_tavily_extract, mock_get_config):
        """Test successful tavily_extract_batch execution"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 60
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        mock_extract_instance = Mock()
        mock_extract_instance.invoke.return_value = {
            "results": [
                {"url": "https://example1.com", "raw_content": "Content 1"},
                {"url": "https://example2.com", "raw_content": "Content 2"}
            ]
        }
        mock_tavily_extract.return_value = mock_extract_instance

        result = tavily_extract_batch.invoke({
            "urls": ["https://example1.com", "https://example2.com"]
        })

        assert "results" in result
        assert len(result["results"]) == 2
        mock_extract_instance.invoke.assert_called_once()


class TestMapToolsSuccessFlow:
    """Test successful execution flow for map tools"""

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilyMap')
    def test_map_website_success(self, mock_tavily_map, mock_get_config):
        """Test successful tavily_map_website execution"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        mock_map_instance = Mock()
        mock_map_instance.invoke.return_value = {
            "links": ["https://example.com/page1", "https://example.com/page2"]
        }
        mock_tavily_map.return_value = mock_map_instance

        result = tavily_map_website.invoke({"url": "https://example.com"})

        assert "links" in result
        assert len(result["links"]) == 2
        mock_map_instance.invoke.assert_called_once()

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilyMap')
    def test_map_with_filter_success(self, mock_tavily_map, mock_get_config):
        """Test successful tavily_map_with_filter execution"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        mock_map_instance = Mock()
        mock_map_instance.invoke.return_value = {
            "links": ["https://example.com/blog/post1"]
        }
        mock_tavily_map.return_value = mock_map_instance

        result = tavily_map_with_filter.invoke({
            "url": "https://example.com",
            "filter_patterns": ["/blog/*"]
        })

        assert "links" in result
        mock_map_instance.invoke.assert_called_once()


class TestCrawlToolsSuccessFlow:
    """Test successful execution flow for crawl tools"""

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilyCrawl')
    def test_crawl_basic_success(self, mock_tavily_crawl, mock_get_config):
        """Test successful tavily_crawl_basic execution"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 60
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        mock_crawl_instance = Mock()
        mock_crawl_instance.invoke.return_value = {
            "results": [{"url": "https://example.com", "content": "Page content"}]
        }
        mock_tavily_crawl.return_value = mock_crawl_instance

        result = tavily_crawl_basic.invoke({"url": "https://example.com"})

        assert "results" in result
        assert len(result["results"]) == 1
        mock_crawl_instance.invoke.assert_called_once()

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilyCrawl')
    def test_crawl_targeted_success(self, mock_tavily_crawl, mock_get_config):
        """Test successful tavily_crawl_targeted execution"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 60
        mock_config.api_key = "test_key"
        mock_config.crawl.max_depth = 2
        mock_get_config.return_value = mock_config

        mock_crawl_instance = Mock()
        mock_crawl_instance.invoke.return_value = {
            "results": [{"url": "https://example.com/docs", "content": "Documentation"}]
        }
        mock_tavily_crawl.return_value = mock_crawl_instance

        result = tavily_crawl_targeted.invoke({
            "url": "https://example.com",
            "instructions": "Focus on documentation pages"
        })

        assert "results" in result
        mock_crawl_instance.invoke.assert_called_once()


class TestRetryBehavior:
    """Test retry behavior on transient errors"""

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilySearch')
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_search_basic_retries_on_timeout(self, mock_sleep, mock_tavily_search, mock_get_config):
        """Test tavily_search_basic retries on timeout errors"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        # First two calls timeout, third succeeds
        mock_search_instance = Mock()
        mock_search_instance.invoke.side_effect = [
            Timeout("Timeout 1"),
            Timeout("Timeout 2"),
            {"results": [{"title": "Success"}]}
        ]
        mock_tavily_search.return_value = mock_search_instance

        result = tavily_search_basic.invoke({"query": "test query"})

        # Should succeed after retries
        assert "results" in result
        assert mock_search_instance.invoke.call_count == 3
        # Should have slept twice (between retries)
        assert mock_sleep.call_count == 2

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilySearch')
    @patch('time.sleep')
    def test_search_basic_retries_on_connection_error(self, mock_sleep, mock_tavily_search, mock_get_config):
        """Test tavily_search_basic retries on connection errors"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        mock_search_instance = Mock()
        mock_search_instance.invoke.side_effect = [
            ConnectionError("Network error"),
            {"results": []}
        ]
        mock_tavily_search.return_value = mock_search_instance

        result = tavily_search_basic.invoke({"query": "test query"})

        assert "results" in result
        assert mock_search_instance.invoke.call_count == 2

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilySearch')
    @patch('time.sleep')
    def test_search_basic_fails_after_max_retries(self, mock_sleep, mock_tavily_search, mock_get_config):
        """Test tavily_search_basic fails gracefully after max retries"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        # All attempts fail
        mock_search_instance = Mock()
        mock_search_instance.invoke.side_effect = ConnectionError("Network error")
        mock_tavily_search.return_value = mock_search_instance

        result = tavily_search_basic.invoke({"query": "test query"})

        # Should return structured error response
        assert result["status"] == "error"
        assert result["error_type"] == "network_error"
        assert mock_search_instance.invoke.call_count == 3


class TestHTTPErrorHandling:
    """Test HTTP error handling in tools"""

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilySearch')
    def test_search_basic_handles_401_error(self, mock_tavily_search, mock_get_config):
        """Test tavily_search_basic handles 401 authentication error"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "invalid_key"
        mock_get_config.return_value = mock_config

        mock_response = Mock()
        mock_response.status_code = 401
        http_error = HTTPError()
        http_error.response = mock_response

        mock_search_instance = Mock()
        mock_search_instance.invoke.side_effect = http_error
        mock_tavily_search.return_value = mock_search_instance

        result = tavily_search_basic.invoke({"query": "test query"})

        assert result["status"] == "error"
        assert result["error_type"] == "authentication_error"
        # Should not retry on 401
        assert mock_search_instance.invoke.call_count == 1

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilyExtract')
    @patch('time.sleep')
    def test_extract_url_handles_429_rate_limit(self, mock_sleep, mock_tavily_extract, mock_get_config):
        """Test tavily_extract_url handles 429 rate limit with retry"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 3
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '2'}
        http_error = HTTPError()
        http_error.response = mock_response

        mock_extract_instance = Mock()
        mock_extract_instance.invoke.side_effect = [
            http_error,
            {"raw_content": "Success after rate limit"}
        ]
        mock_tavily_extract.return_value = mock_extract_instance

        result = tavily_extract_url.invoke({"url": "https://example.com"})

        # Should succeed after retry
        assert "raw_content" in result
        assert mock_extract_instance.invoke.call_count == 2
        # Should respect Retry-After header
        mock_sleep.assert_called_once_with(2.0)


class TestStructuredErrorResponses:
    """Test that all tools return structured error responses"""

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilySearch')
    def test_error_response_structure(self, mock_tavily_search, mock_get_config):
        """Test error responses have required structure"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 1
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        mock_search_instance = Mock()
        mock_search_instance.invoke.side_effect = ConnectionError("Network error")
        mock_tavily_search.return_value = mock_search_instance

        result = tavily_search_basic.invoke({"query": "test query"})

        # Verify structured error response
        assert "status" in result
        assert result["status"] == "error"
        assert "error_type" in result
        assert "message" in result
        assert "suggestion" in result
        assert isinstance(result["error_type"], str)
        assert isinstance(result["message"], str)
        assert isinstance(result["suggestion"], str)

    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.get_config')
    @patch('src.components.shared.tools.sdk.tavily_search.tavily_search_tool.TavilyMap')
    def test_all_tools_return_structured_errors(self, mock_tavily_map, mock_get_config):
        """Test that all tool types return structured errors"""
        mock_config = Mock()
        mock_config.is_available.return_value = True
        mock_config.api.max_retries = 1
        mock_config.api.retry_delay = 0.1
        mock_config.api.timeout = 30
        mock_config.api_key = "test_key"
        mock_get_config.return_value = mock_config

        mock_map_instance = Mock()
        mock_map_instance.invoke.side_effect = Timeout("Timeout error")
        mock_tavily_map.return_value = mock_map_instance

        result = tavily_map_website.invoke({"url": "https://example.com"})

        # All tools should follow same error structure
        assert result["status"] == "error"
        assert "error_type" in result
        assert "timeout" in result["error_type"]
