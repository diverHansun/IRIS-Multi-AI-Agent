"""JSON Arguments Parser Middleware for Deep Agents.

This middleware automatically parses JSON string arguments to Python objects
before tool execution. This is needed because in Deep mode, LLM-generated tool
arguments are sometimes serialized as JSON strings instead of native Python objects.

Example:
    Deep mode may pass: {"config": '{"key": "value"}'}  (string)
    This middleware converts to: {"config": {"key": "value"}}  (dict)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

logger = logging.getLogger(__name__)


class JsonArgsParserMiddleware(AgentMiddleware):
    """Middleware to automatically parse JSON string arguments in tool calls.

    This middleware intercepts tool calls and attempts to parse any string arguments
    that appear to be JSON-encoded. This solves the common issue where LLM models
    (especially in deep agent mode) pass configuration objects as JSON strings
    instead of native Python dictionaries.

    The parsing is conservative:
    - Only attempts to parse string values
    - Silently keeps original value if JSON parsing fails
    - Does not recurse into nested structures
    - Does not modify non-string values

    Example:
        >>> # Tool receives: {"urls": ["http://..."], "config": '{"timeout": 30}'}
        >>> # After middleware: {"urls": ["http://..."], "config": {"timeout": 30}}
    """

    def __init__(self, *, enable_logging: bool = False):
        """Initialize the JSON arguments parser middleware.

        Args:
            enable_logging: If True, log all argument conversions at DEBUG level.
                          Default is False to avoid verbose logs.
        """
        super().__init__()
        self.enable_logging = enable_logging

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> ToolMessage | Command:
        """Intercept tool call and parse JSON string arguments.

        Args:
            request: Tool call request containing tool_call dict with args.
            handler: Handler function to execute the actual tool.

        Returns:
            Result from the tool handler (ToolMessage or Command).
        """
        self._parse_json_args(request)
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> ToolMessage | Command:
        """Async version of wrap_tool_call.

        Args:
            request: Tool call request containing tool_call dict with args.
            handler: Async handler function to execute the actual tool.

        Returns:
            Result from the tool handler (ToolMessage or Command).
        """
        self._parse_json_args(request)
        return await handler(request)

    def _parse_json_args(self, request: ToolCallRequest) -> None:
        """Parse JSON strings in tool call arguments.

        This method modifies request.tool_call["args"] in-place, replacing
        any JSON string values with their parsed equivalents.

        Args:
            request: Tool call request to process.
        """
        args = request.tool_call.get("args", {})
        tool_name = request.tool_call.get("name", "unknown")

        if not isinstance(args, dict):
            # Args should always be a dict, but handle edge case
            return

        conversions = []

        for key, value in args.items():
            if isinstance(value, str):
                # Attempt to parse as JSON
                try:
                    parsed = json.loads(value)
                    args[key] = parsed
                    conversions.append(f"{key}: str -> {type(parsed).__name__}")
                except (json.JSONDecodeError, ValueError):
                    # Not valid JSON, keep original string value
                    pass

        # Log conversions if enabled
        if self.enable_logging and conversions:
            logger.info(
                f"JsonArgsParserMiddleware: Tool '{tool_name}' "
                f"- Parsed {len(conversions)} argument(s): {', '.join(conversions)}"
            )
