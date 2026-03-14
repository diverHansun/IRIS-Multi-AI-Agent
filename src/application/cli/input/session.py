"""
Prompt input factory.

Assembles history, completer, auto-suggest, and key bindings into a single
object that main.py can call as:

    prompt_input = create_prompt_input(ctx)
    query = await prompt_input.prompt_async(plain_prompt)

Naming note:
    "PromptInput" and "create_prompt_input" are deliberately distinct from
    AppState.session_manager / SessionManager, which refer to LLM conversation
    sessions. This object manages terminal line-editing only.

Fallback:
    If prompt_toolkit initialisation fails for any reason, create_prompt_input
    returns a _FallbackInput that wraps rich.Console.input() with the same
    interface. The caller in main.py requires no awareness of which path was taken.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.application.cli.state import AppState

logger = logging.getLogger(__name__)


@runtime_checkable
class PromptInput(Protocol):
    """Interface contract for the prompt input object used by _cli_loop."""

    async def prompt_async(self, message: str, **kwargs) -> str: ...


def create_prompt_input(ctx: "AppState") -> PromptInput:
    """Create and return a PromptInput instance for the CLI loop.

    Called once before the while loop in _cli_loop so that the PromptSession
    (and its history state) persists across the entire session lifetime.
    """
    try:
        return _build_prompt_session(ctx)
    except Exception as exc:
        logger.warning(
            "prompt_toolkit initialisation failed (%s); falling back to console.input().",
            exc,
        )
        return _FallbackInput(ctx)


def _build_prompt_session(ctx: "AppState") -> "PromptInput":
    from prompt_toolkit import PromptSession

    from .completer import CommandCompleter
    from .history import HistoryPathResolver
    from .keybindings import build_key_bindings
    from .suggest import CommandAutoSuggest

    return PromptSession(
        history=HistoryPathResolver().resolve(ctx),
        completer=CommandCompleter(ctx),
        auto_suggest=CommandAutoSuggest(),
        key_bindings=build_key_bindings(),
        # Tab-only completion — does not interfere with free-text AI queries.
        complete_while_typing=False,
        # Enable Ctrl+R reverse history search.
        enable_history_search=True,
        # Maximum lines reserved for the completion menu.
        reserve_space_for_menu=6,
    )


class _FallbackInput:
    """Graceful degradation wrapper around rich.Console.input().

    Provides the same prompt_async interface as PromptSession so that
    main.py requires no conditional logic for the fallback path.

    Handles FormattedText gracefully by extracting plain text,
    since rich.Console.input() only accepts str.
    """

    def __init__(self, ctx: "AppState") -> None:
        self._console = ctx.console

    async def prompt_async(self, message, **_) -> str:
        if not isinstance(message, str):
            # Extract plain text from FormattedText (list of (style, text) tuples).
            message = "".join(text for _, text in message)
        return await asyncio.to_thread(self._console.input, message)
