"""
Unit tests for MCP tool error handling wrapper.

Tests the _wrap_mcp_tool_with_error_handling function in GlobalMCPManager
to ensure network errors and timeouts are gracefully converted to error messages
instead of raising exceptions that interrupt Deep Agent conversations.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.components.shared.tools.mcp.manager import _wrap_mcp_tool_with_error_handling

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


class MockToolArgs(BaseModel):
    """Mock arguments schema for testing."""
    query: str = Field(description="Test query parameter")


class TestMCPErrorHandling:
    """Test suite for MCP tool error handling wrapper."""

    @pytest.fixture
    def mock_tool(self):
        """Create a mock MCP tool for testing."""
        async def mock_coroutine(**kwargs):
            return "Success result"

        tool = StructuredTool.from_function(
            name="test_mcp_tool",
            func=None,
            coroutine=mock_coroutine,
            description="Test MCP tool",
            args_schema=MockToolArgs,
        )
        return tool

    @pytest.mark.asyncio
    async def test_successful_execution(self, mock_tool):
        """Test that successful tool execution returns original result."""
        wrapped_tool = _wrap_mcp_tool_with_error_handling(mock_tool)

        result = await wrapped_tool.coroutine(query="test")

        assert result == "Success result"
        assert wrapped_tool.name == "test_mcp_tool"
        assert wrapped_tool.description == "Test MCP tool"
        assert wrapped_tool.args_schema == MockToolArgs

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, mock_tool):
        """Test that TimeoutError is converted to error message."""
        async def timeout_coroutine(**kwargs):
            raise asyncio.TimeoutError("Connection timeout")

        mock_tool.coroutine = timeout_coroutine
        wrapped_tool = _wrap_mcp_tool_with_error_handling(mock_tool)

        result = await wrapped_tool.coroutine(query="test")

        assert isinstance(result, str)
        assert "[MCP TIMEOUT]" in result
        assert "test_mcp_tool" in result
        assert "execution timed out" in result
        assert "Try again with a simpler request" in result

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, mock_tool):
        """Test that ConnectionError is converted to error message."""
        async def connection_error_coroutine(**kwargs):
            raise ConnectionError("Network unreachable")

        mock_tool.coroutine = connection_error_coroutine
        wrapped_tool = _wrap_mcp_tool_with_error_handling(mock_tool)

        result = await wrapped_tool.coroutine(query="test")

        assert isinstance(result, str)
        assert "[MCP CONNECTION ERROR]" in result
        assert "test_mcp_tool" in result
        assert "connection failed" in result
        assert "ConnectionError: Network unreachable" in result
        assert "Network connectivity issues" in result

    @pytest.mark.asyncio
    async def test_oserror_handling(self, mock_tool):
        """Test that OSError is converted to error message."""
        async def os_error_coroutine(**kwargs):
            raise OSError("Process terminated unexpectedly")

        mock_tool.coroutine = os_error_coroutine
        wrapped_tool = _wrap_mcp_tool_with_error_handling(mock_tool)

        result = await wrapped_tool.coroutine(query="test")

        assert isinstance(result, str)
        assert "[MCP CONNECTION ERROR]" in result
        assert "test_mcp_tool" in result
        assert "OSError: Process terminated unexpectedly" in result

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, mock_tool):
        """Test that generic Exception is converted to error message."""
        async def generic_error_coroutine(**kwargs):
            raise ValueError("Invalid parameter value")

        mock_tool.coroutine = generic_error_coroutine
        wrapped_tool = _wrap_mcp_tool_with_error_handling(mock_tool)

        result = await wrapped_tool.coroutine(query="test")

        assert isinstance(result, str)
        assert "[MCP ERROR]" in result
        assert "test_mcp_tool" in result
        assert "ValueError" in result
        assert "Invalid parameter value" in result
        assert "temporarily unavailable" in result

    @pytest.mark.asyncio
    async def test_preserves_tool_metadata(self, mock_tool):
        """Test that wrapper preserves original tool metadata."""
        wrapped_tool = _wrap_mcp_tool_with_error_handling(mock_tool)

        assert wrapped_tool.name == mock_tool.name
        assert wrapped_tool.description == mock_tool.description
        assert wrapped_tool.args_schema == mock_tool.args_schema

    @pytest.mark.asyncio
    async def test_fallback_to_sync_function(self):
        """Test fallback to sync function when coroutine is not available."""
        def sync_function(query: str) -> str:
            return f"Sync result: {query}"

        tool = StructuredTool.from_function(
            name="sync_tool",
            func=sync_function,
            description="Sync test tool",
            args_schema=MockToolArgs,
        )

        wrapped_tool = _wrap_mcp_tool_with_error_handling(tool)

        result = await wrapped_tool.coroutine(query="test")

        assert result == "Sync result: test"

    @pytest.mark.asyncio
    async def test_no_callable_raises_error(self):
        """Test that tool with no callable implementation returns error message."""
        # Create a tool with a coroutine, then manually remove it to simulate edge case
        async def temp_coroutine(**kwargs):
            return "temp"

        tool = StructuredTool.from_function(
            name="empty_tool",
            func=None,
            coroutine=temp_coroutine,
            description="Empty tool",
            args_schema=MockToolArgs,
        )

        # Remove both callables to simulate edge case
        tool.coroutine = None
        tool.func = None

        wrapped_tool = _wrap_mcp_tool_with_error_handling(tool)

        result = await wrapped_tool.coroutine(query="test")

        assert isinstance(result, str)
        assert "[MCP ERROR]" in result
        assert "empty_tool" in result
        assert "RuntimeError" in result

    @pytest.mark.asyncio
    async def test_multiple_sequential_calls(self, mock_tool):
        """Test that wrapper handles multiple sequential calls correctly."""
        call_count = 0

        async def counting_coroutine(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("First call fails")
            return f"Success on call {call_count}"

        mock_tool.coroutine = counting_coroutine
        wrapped_tool = _wrap_mcp_tool_with_error_handling(mock_tool)

        # First call should return error message
        result1 = await wrapped_tool.coroutine(query="test1")
        assert "[MCP CONNECTION ERROR]" in result1

        # Second call should succeed
        result2 = await wrapped_tool.coroutine(query="test2")
        assert result2 == "Success on call 2"

    @pytest.mark.asyncio
    async def test_error_message_structure(self, mock_tool):
        """Test that error messages have consistent structure."""
        async def error_coroutine(**kwargs):
            raise ConnectionError("Test error")

        mock_tool.coroutine = error_coroutine
        wrapped_tool = _wrap_mcp_tool_with_error_handling(mock_tool)

        result = await wrapped_tool.coroutine(query="test")

        # Verify error message structure
        assert result.startswith("[MCP CONNECTION ERROR]")
        assert "Tool 'test_mcp_tool'" in result
        assert "Error details:" in result
        assert "Possible causes:" in result
        assert "Suggestions:" in result
