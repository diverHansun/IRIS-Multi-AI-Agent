"""
Conversation handling utilities for the agent engine basic mode.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.components.shared.memory.session_context import SessionContext

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

    with ctx.console.status("[dim]Agent reasoning...[/]"):
        result = await agent.ainvoke(query, session_id=ctx.session_id)

    # Persist conversation to storage if memory sync is available
    if hasattr(ctx, 'memory_sync') and ctx.memory_sync:
        try:
            session_ctx = SessionContext(
                session_id=ctx.session_id,
                agent_type=config.get("agent_type", "basic"),
                provider=config.get("provider", "unknown"),
                function_type="agent",
            )
            ctx.memory_sync.persist_from_runtime(
                session_ctx,
                agent.checkpointer if hasattr(agent, 'checkpointer') else None,
                None,
                result,
            )
            logger.debug(f"Persisted Basic mode conversation for session {ctx.session_id}")
        except Exception as e:
            logger.warning(f"Failed to persist Basic mode conversation: {e}")

    if result.get("success"):
        answer = result.get("output", "No response generated.")
        ctx.console.print(f"[bold blue]BasicAgent >[/] {answer}")
        tool_calls = result.get("tool_calls", 0)
        if tool_calls:
            tool_names = result.get("tool_names") or []
            if tool_names:
                # Display unique tool count and names
                ctx.console.print(f"[dim]Used {len(tool_names)} tools ({tool_calls} calls): {', '.join(tool_names)}[/]")
            else:
                ctx.console.print(f"[dim]Used {tool_calls} tool calls[/]")
        return answer

    error_message = result.get("error", "Unknown error")
    ctx.console.print(f"[bold red]Agent Error: {error_message}[/]")
    return ""
