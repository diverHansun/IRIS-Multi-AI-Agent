"""Deep agent conversation helpers."""

from __future__ import annotations

from typing import Any, Dict


def _get_agent_config(ctx) -> Dict[str, Any]:
    return ctx.get_engine_config("agent")


async def handle_deep_agent_query(ctx, query: str) -> str:
    """Route query to deep agent instance."""
    config = _get_agent_config(ctx)
    agent: Any = config.get("agent_instance")
    if agent is None:
        raise RuntimeError("Deep agent is not initialized.")

    with ctx.console.status("[dim]Deep agent reasoning...[/]"):
        result = await agent.ainvoke(query, session_id=ctx.session_id)

    if result.get("success"):
        answer = result.get("output", "No response generated.")
        ctx.console.print(f"[bold blue]DeepAgent >[/] {answer}")

        # Display subagent delegations if any
        subagent_calls = result.get("subagent_calls", [])
        if subagent_calls:
            ctx.console.print(f"[bold cyan]SubAgent Delegations:[/]")
            for call in subagent_calls:
                subagent_type = call.get("subagent_type", "unknown")
                description = call.get("description", "")
                ctx.console.print(f"  [cyan]→ {subagent_type}:[/] {description}")

        # Display tool usage
        tool_calls = result.get("tool_calls", 0)
        if tool_calls:
            tool_names = result.get("tool_names") or []
            if tool_names:
                # Display unique tool count and names
                ctx.console.print(f"[dim]Used {len(tool_names)} tools ({tool_calls} calls): {', '.join(tool_names)}[/]")
            else:
                ctx.console.print(f"[dim]Used {tool_calls} tool calls[/]")
        return answer

    error_message = result.get("output", "Unknown deep agent error.")
    ctx.console.print(f"[bold red]Deep Agent Error: {error_message}[/]")
    return ""
