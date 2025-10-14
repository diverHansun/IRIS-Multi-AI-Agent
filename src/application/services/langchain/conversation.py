"""
Conversation handling utilities for the LangChain engine.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.messages import HumanMessage

from .streaming import stream_response


def _get_langchain_config(ctx) -> Dict[str, Any]:
    return ctx.get_engine_config("langchain")


def _build_context(history_messages: List[Any]) -> str:
    context_text: list[str] = []
    for message in history_messages[-6:]:
        speaker = "User" if isinstance(message, HumanMessage) else "AI"
        content = getattr(message, "content", "")
        context_text.append(f"{speaker}: {content}")
    return "\n".join(context_text)


async def handle_llm_query(ctx, query: str, streaming: bool = True) -> str:
    """
    Handle an LLM-style query with optional streaming output.
    """
    config = _get_langchain_config(ctx)
    agent = config.get("agent")
    if agent is None:
        raise RuntimeError("LangChain agent is not initialized.")

    if not hasattr(agent, "get_llm"):
        raise RuntimeError("Current agent does not expose an LLM instance.")

    llm = agent.get_llm()
    if llm is None:
        raise RuntimeError("Unable to acquire LLM instance from agent.")

    info = agent.get_info() if hasattr(agent, "get_info") else {}
    provider = info.get("provider", "unknown")

    history = ctx.global_memory.get_session_history(ctx.session_id) if ctx.global_memory else None
    context_messages = history.messages[-10:] if history and getattr(history, "messages", None) else []

    prompt = query
    if context_messages:
        context_text = _build_context(context_messages)
        prompt = f"History:\n{context_text}\n\nCurrent Question: {query}"

    if streaming:
        ctx.console.print("[dim]LLM streaming generation...[/]")
        answer = await stream_response(
            provider=provider,
            prompt=prompt,
            llm=llm,
            display_title=f"LLM Response ({provider})",
            show_display=True,
        )
    else:
        with ctx.console.status("[dim]LLM thinking...[/]"):
            response = await llm.ainvoke([HumanMessage(content=prompt)])
        answer = response.content if hasattr(response, "content") else str(response)
        ctx.console.print(f"[bold green]LLM >[/] {answer}")

    if ctx.global_memory:
        ctx.global_memory.add_llm_conversation(ctx.session_id, query, answer)

    return answer


async def handle_agent_query(ctx, query: str) -> str:
    """
    Handle an agent-style query where tool usage may occur.
    """
    config = _get_langchain_config(ctx)
    agent = config.get("agent")
    if agent is None:
        raise RuntimeError("LangChain agent is not initialized.")

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
