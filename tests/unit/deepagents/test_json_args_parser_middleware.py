"""Unit tests for JsonArgsParserMiddleware."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import ToolMessage
from src.components.deepagents.runtime_middlewares.json_args_parser import JsonArgsParserMiddleware


class TestJsonArgsParserMiddleware:
    """Test suite for JsonArgsParserMiddleware."""

    def setup_method(self):
        """Set up test fixtures."""
        self.middleware = JsonArgsParserMiddleware()

    def create_mock_request(self, args):
        """Create a mock ToolCallRequest with given args."""
        request = MagicMock()
        request.tool_call = {
            "name": "test_tool",
            "args": args,
            "id": "test_id_123"
        }
        request.tool = None
        request.state = {}
        request.runtime = None
        return request

    def test_parse_json_string_to_dict(self):
        """Test that JSON string is correctly parsed to dict."""
        args = {
            "url": "https://example.com",
            "config": '{"timeout": 30, "retry": true}'
        }
        request = self.create_mock_request(args)

        # Create mock handler
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        # Execute middleware
        self.middleware.wrap_tool_call(request, handler)

        # Verify JSON string was parsed
        assert isinstance(request.tool_call["args"]["config"], dict)
        assert request.tool_call["args"]["config"] == {"timeout": 30, "retry": True}
        # Verify non-JSON string unchanged
        assert request.tool_call["args"]["url"] == "https://example.com"

    def test_dict_passthrough(self):
        """Test that dict arguments are not modified."""
        args = {
            "url": "https://example.com",
            "config": {"timeout": 30, "retry": True}
        }
        request = self.create_mock_request(args)
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        self.middleware.wrap_tool_call(request, handler)

        # Verify dict remains unchanged
        assert isinstance(request.tool_call["args"]["config"], dict)
        assert request.tool_call["args"]["config"] == {"timeout": 30, "retry": True}

    def test_plain_string_preserved(self):
        """Test that plain strings are not modified."""
        args = {
            "message": "Hello, World!",
            "url": "https://example.com"
        }
        request = self.create_mock_request(args)
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        self.middleware.wrap_tool_call(request, handler)

        # Verify strings remain unchanged
        assert request.tool_call["args"]["message"] == "Hello, World!"
        assert request.tool_call["args"]["url"] == "https://example.com"

    def test_invalid_json_preserved(self):
        """Test that invalid JSON strings are preserved."""
        args = {
            "config": '{"invalid json syntax{'
        }
        request = self.create_mock_request(args)
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        self.middleware.wrap_tool_call(request, handler)

        # Verify invalid JSON remains as string
        assert request.tool_call["args"]["config"] == '{"invalid json syntax{'

    def test_empty_string_preserved(self):
        """Test that empty strings are preserved."""
        args = {
            "value": ""
        }
        request = self.create_mock_request(args)
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        self.middleware.wrap_tool_call(request, handler)

        # Verify empty string preserved
        assert request.tool_call["args"]["value"] == ""

    def test_mixed_parameters(self):
        """Test mixed parameter types are handled correctly."""
        args = {
            "urls": ["https://example.com"],
            "browser_config": '{"headless": true}',
            "crawler_config": '{"word_count_threshold": 10}',
            "http_config": "{}",
            "plain_string": "some text",
            "number": 42,
            "boolean": True,
            "none_value": None,
            "dict_param": {"existing": "dict"}
        }
        request = self.create_mock_request(args)
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        self.middleware.wrap_tool_call(request, handler)

        # Verify each type handled correctly
        assert request.tool_call["args"]["urls"] == ["https://example.com"]
        assert request.tool_call["args"]["browser_config"] == {"headless": True}
        assert request.tool_call["args"]["crawler_config"] == {"word_count_threshold": 10}
        assert request.tool_call["args"]["http_config"] == {}
        assert request.tool_call["args"]["plain_string"] == "some text"
        assert request.tool_call["args"]["number"] == 42
        assert request.tool_call["args"]["boolean"] is True
        assert request.tool_call["args"]["none_value"] is None
        assert request.tool_call["args"]["dict_param"] == {"existing": "dict"}

    def test_json_primitives(self):
        """Test JSON primitive values are parsed correctly."""
        args = {
            "bool_true": "true",
            "bool_false": "false",
            "null_value": "null",
            "number": "123",
            "float_num": "45.67"
        }
        request = self.create_mock_request(args)
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        self.middleware.wrap_tool_call(request, handler)

        # Verify primitives parsed correctly
        assert request.tool_call["args"]["bool_true"] is True
        assert request.tool_call["args"]["bool_false"] is False
        assert request.tool_call["args"]["null_value"] is None
        assert request.tool_call["args"]["number"] == 123
        assert request.tool_call["args"]["float_num"] == 45.67

    def test_handler_called_with_modified_request(self):
        """Test that handler is called with the modified request."""
        args = {
            "config": '{"key": "value"}'
        }
        request = self.create_mock_request(args)
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        result = self.middleware.wrap_tool_call(request, handler)

        # Verify handler was called
        handler.assert_called_once_with(request)
        # Verify result is from handler
        assert isinstance(result, ToolMessage)
        assert result.content == "success"

    @pytest.mark.asyncio
    async def test_async_wrap_tool_call(self):
        """Test async version of wrap_tool_call."""
        args = {
            "config": '{"timeout": 30}'
        }
        request = self.create_mock_request(args)
        handler = AsyncMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        result = await self.middleware.awrap_tool_call(request, handler)

        # Verify JSON was parsed
        assert request.tool_call["args"]["config"] == {"timeout": 30}
        # Verify handler was called
        handler.assert_called_once_with(request)
        # Verify result
        assert isinstance(result, ToolMessage)
        assert result.content == "success"

    def test_empty_args(self):
        """Test handling of empty args dict."""
        args = {}
        request = self.create_mock_request(args)
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        self.middleware.wrap_tool_call(request, handler)

        # Should not raise exception
        assert request.tool_call["args"] == {}

    def test_non_dict_args(self):
        """Test handling of non-dict args (edge case)."""
        request = MagicMock()
        request.tool_call = {
            "name": "test_tool",
            "args": "not_a_dict",  # Edge case: args is not a dict
            "id": "test_id_123"
        }
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        # Should not raise exception, just skip processing
        self.middleware.wrap_tool_call(request, handler)
        handler.assert_called_once()

    def test_logging_disabled_by_default(self):
        """Test that logging is disabled by default."""
        middleware = JsonArgsParserMiddleware()
        assert middleware.enable_logging is False

    def test_logging_can_be_enabled(self):
        """Test that logging can be enabled via constructor."""
        middleware = JsonArgsParserMiddleware(enable_logging=True)
        assert middleware.enable_logging is True

    def test_real_crawl4ai_example(self):
        """Test with real crawl4ai tool call example from the error log."""
        args = {
            'urls': ['https://www.marxists.org/chinese/maozedong/index.htm#5'],
            'browser_config': '{"headless": true}',
            'crawler_config': '{"word_count_threshold": 10}',
            'http_config': '{}',
            'geolocation_config': '{}',
            'proxy_config': '{}',
            'virtual_scroll_config': '{}',
            'link_preview_config': '{}',
            'llm_config': '{}',
            'seeding_config': '{}'
        }
        request = self.create_mock_request(args)
        handler = MagicMock(return_value=ToolMessage(content="success", tool_call_id="test_id_123"))

        self.middleware.wrap_tool_call(request, handler)

        # Verify all JSON strings parsed to dicts
        assert isinstance(request.tool_call["args"]["browser_config"], dict)
        assert request.tool_call["args"]["browser_config"] == {"headless": True}
        assert isinstance(request.tool_call["args"]["crawler_config"], dict)
        assert request.tool_call["args"]["crawler_config"] == {"word_count_threshold": 10}
        assert isinstance(request.tool_call["args"]["http_config"], dict)
        assert request.tool_call["args"]["http_config"] == {}
        # Verify list unchanged
        assert request.tool_call["args"]["urls"] == ['https://www.marxists.org/chinese/maozedong/index.htm#5']
