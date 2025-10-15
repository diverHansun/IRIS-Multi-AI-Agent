"""
Agent streaming management helpers.
"""

from __future__ import annotations

from typing import Any, Optional

from src.llm.utils import stream_llm_response, streaming_manager


async def stream_response(
    provider: str,
    prompt: str,
    llm: Any,
    display_title: str | None = None,
    show_display: bool = True,
) -> str:
    """
    Stream a response from the LLM using the shared streaming utilities.
    """
    return await stream_llm_response(
        provider=provider,
        prompt=prompt,
        llm=llm,
        display_title=display_title,
        show_display=show_display,
    )


def register_llm(provider: str, llm: Optional[Any]) -> None:
    """
    Register an LLM instance for future streaming sessions.
    """
    if not llm:
        return
    streaming_manager.register_llm(provider, llm)

