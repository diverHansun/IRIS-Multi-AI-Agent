from __future__ import annotations

from typing import Any, Optional

from src.llm.utils import stream_llm_response, streaming_manager


async def stream_response(
    provider: str,
    prompt: str,
    llm: Any,
    display_title: str | None = None,
    show_display: bool = True,
    renderer: Any | None = None,
) -> str:
    return await stream_llm_response(
        provider=provider,
        prompt=prompt,
        llm=llm,
        display_title=display_title,
        show_display=show_display,
        renderer=renderer,
    )


def register_llm(provider: str, llm: Optional[Any]) -> None:
    if not llm:
        return
    streaming_manager.register_llm(provider, llm)
