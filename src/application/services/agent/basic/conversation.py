"""
Conversation handling utilities for the agent engine basic mode.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from src.application.cli.renderers import BasicTranscriptRenderer

logger = logging.getLogger(__name__)


def _get_agent_config(ctx) -> Dict[str, Any]:
    return ctx.get_engine_config("agent")


async def handle_agent_query(ctx, query: str) -> str:
    """
    Handle an agent-oriented query where tool usage is permitted.
    """
    config = _get_agent_config(ctx)
    agent = config.get("agent_instance")
    if agent is None:
        raise RuntimeError("Agent engine is not initialized.")
    renderer = BasicTranscriptRenderer(ctx.console)

    try:
        renderer.start_spinner()
        result = await agent.ainvoke(query, session_id=ctx.session_id)
        renderer.stop_spinner()

        if result.get("success"):
            answer = result.get("output", "No response generated.")
            renderer.emit_assistant_text(answer)
            tool_calls = result.get("tool_calls", 0)
            if tool_calls:
                renderer.emit_summary(
                    {
                        "tool_calls": tool_calls,
                        "tool_names": result.get("tool_names") or [],
                    }
                )
            return answer

        error_message = result.get("error", "Unknown error")
        renderer.emit_error(f"Agent Error: {error_message}")
        return ""

    except KeyboardInterrupt:
        renderer.stop_spinner()
        renderer.emit_warning("\nAgent execution interrupted by user.")
        logger.info("BasicAgent execution interrupted by user via Ctrl+C")
        return ""
    except asyncio.CancelledError:
        renderer.stop_spinner()
        renderer.emit_warning("\nAgent execution cancelled.")
        logger.info("BasicAgent execution cancelled")
        return ""
