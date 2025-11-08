"""Custom middleware implementations used by the DeepAgents runtime.

These classes intentionally avoid importing the official `deepagents` package so that
we retain full control over prompting and configuration.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain_core.messages import RemoveMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from .json_args_parser import JsonArgsParserMiddleware
from .timeout import ExecutionTimeoutMiddleware

logger = logging.getLogger(__name__)

__all__ = [
    "JsonArgsParserMiddleware",
    "PatchToolCallsMiddleware",
    "ExecutionTimeoutMiddleware",
]


class PatchToolCallsMiddleware(AgentMiddleware):
    """Patch dangling tool calls to keep conversation history consistent."""

    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        messages = state["messages"]
        if not messages:
            return None

        patched_messages = []
        patch_count = 0

        for idx, msg in enumerate(messages):
            patched_messages.append(msg)
            if msg.type == "ai" and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    corresponding = next(
                        (
                            candidate
                            for candidate in messages[idx:]
                            if candidate.type == "tool" and candidate.tool_call_id == tool_call["id"]
                        ),
                        None,
                    )
                    if corresponding is None:
                        patch_count += 1
                        logger.debug(
                            f"Patching dangling tool call: {tool_call['name']} (id: {tool_call['id']})"
                        )
                        patched_messages.append(
                            ToolMessage(
                                content=(
                                    f"Tool call {tool_call['name']} with id {tool_call['id']} "
                                    "was cancelled before completion."
                                ),
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                        )

        # Only return patched messages if any patches were made
        if patch_count == 0:
            logger.debug("No dangling tool calls found, skipping message rebuild")
            return None

        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *patched_messages]}
