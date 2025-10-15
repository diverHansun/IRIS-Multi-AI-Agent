"""
Conversation handling utilities for the agent engine basic mode.
"""

from __future__ import annotations

from typing import Any, Dict


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

    if result.get("success"):
        answer = result.get("output", "No response generated.")
        ctx.console.print(f"[bold blue]Agent >[/] {answer}")
        tool_calls = result.get("tool_calls", 0)
        if tool_calls:
            tool_names = result.get("tool_names") or []
            if tool_names:
                ctx.console.print(f"[dim]Used {tool_calls} tool calls: {', '.join(tool_names)}[/]")
            else:
                ctx.console.print(f"[dim]Used {tool_calls} tool calls[/]")
        return answer

    error_message = result.get("error", "Unknown error")
    ctx.console.print(f"[bold red]Agent Error: {error_message}[/]")
    return ""
