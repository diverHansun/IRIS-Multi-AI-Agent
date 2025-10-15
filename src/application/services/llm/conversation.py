from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.messages import HumanMessage

from .streaming import stream_response


def _build_context(history_messages: List[Any]) -> str:
    lines: list[str] = []
    for message in history_messages[-6:]:
        speaker = "User" if isinstance(message, HumanMessage) else "AI"
        content = getattr(message, "content", "")
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


async def handle_llm_query(
    ctx,
    llm,
    provider: str,
    query: str,
    *,
    streaming: bool = True,
) -> str:
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
