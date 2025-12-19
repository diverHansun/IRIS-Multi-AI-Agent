"""
Refactored CLI main loop entrypoint.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from src.components.shared.memory import (
    SessionManager,
    LLMMemory,
    BasicAgentCheckpointer,
    DeepAgentCheckpointer,
)

from src.application.commands import dispatch
from src.application.commands.parser import extract_command_name, is_command, parse_command
from src.application.engine_adapters import get_adapter
from src.application.services import get_current_service
from src.application.services.agent.deep.hitl.session_manager import SessionHITLManager
from src.application.cli.gui import formatter as gui_formatter
from src.application.cli.gui import render as gui_render
from src.application.cli.gui import logo as gui_logo
from rich.markup import escape
from src.application.cli.theme import COLORS

from src.application.cli.state import AppState
from src.components.deepagents.runtime_middlewares.timeout import ExecutionTimeoutError

logger = logging.getLogger(__name__)

try:
    from src.components.shared.tools.mcp import GlobalMCPManager
    MCP_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    GlobalMCPManager = None
    MCP_AVAILABLE = False


async def run() -> None:
    """
    Entrypoint for the CLI main loop.
    """
    ctx = AppState()
    if MCP_AVAILABLE:
        ctx.mcp_manager = GlobalMCPManager

    gui_logo.display_logo(ctx.console)
    gui_logo.display_logo_intro(ctx.console)
    gui_render.print_welcome(ctx.console)

    try:
        _initialize_memory(ctx)

        service = get_current_service(ctx)
        init_result = await service.initialize(ctx)
        if _handle_service_result(ctx, init_result):
            await _cli_loop(ctx)
    finally:
        await _cleanup_engines(ctx)


async def shutdown(waiter: Optional[asyncio.Task] = None) -> None:
    """
    Gracefully stop any outstanding asynchronous tasks that belong to the CLI.
    """
    if waiter is not None:
        await waiter


def _initialize_memory(ctx: AppState) -> None:
    """
    Initialize memory system with basic/llm mode by default.

    Deep mode will create its own isolated memory manager during agent initialization.
    Following SRP: CLI manages basic/llm memory, deep agent manages deep memory.
    """
    ctx.console.print("Initializing memory system...", style=COLORS["warning"])
    # Initialize for basic/llm modes (isolated storage per mode)
    ctx.session_manager = SessionManager(mode="basic")
    ctx.basic_checkpointer = BasicAgentCheckpointer()
    ctx.llm_memory = LLMMemory()
    ctx.deep_checkpointer = None

    ctx.session_id = ctx.session_manager.prompt_for_session_choice()
    ctx.console.print(f"Current Session ID: {ctx.session_id}", style=COLORS["text_dim"])
    ctx.hitl_manager = SessionHITLManager()


async def _cli_loop(ctx: AppState) -> None:
    while True:
        try:
            prompt = _build_prompt(ctx)
            query = await asyncio.to_thread(ctx.console.input, prompt)
            if ctx.exit_hint_handle:
                ctx.exit_hint_handle.cancel()
                ctx.exit_hint_handle = None
            ctx.exit_hint_until = None
            if not query.strip():
                continue

            if not is_command(query):
                await _handle_conversation(ctx, query)
                continue

            command, args = parse_command(query)
            command_name = extract_command_name(command)
            result = await dispatch(command_name, ctx, args)
            should_exit = _handle_command_result(ctx, command_name, result)
            if should_exit:
                break

        except KeyboardInterrupt:
            now = time.monotonic()
            if ctx.exit_hint_until and now < ctx.exit_hint_until:
                if ctx.exit_hint_handle:
                    ctx.exit_hint_handle.cancel()
                    ctx.exit_hint_handle = None
                ctx.exit_hint_until = None
                ctx.console.print("\nGoodbye!", style=COLORS["info"])
                break

            EXIT_CONFIRM_WINDOW = 3.0
            ctx.exit_hint_until = now + EXIT_CONFIRM_WINDOW

            if ctx.exit_hint_handle:
                ctx.exit_hint_handle.cancel()

            loop = asyncio.get_running_loop()

            def clear_hint() -> None:
                if ctx.exit_hint_until and time.monotonic() >= ctx.exit_hint_until:
                    ctx.exit_hint_until = None
                    ctx.exit_hint_handle = None

            ctx.exit_hint_handle = loop.call_later(EXIT_CONFIRM_WINDOW, clear_hint)

            ctx.console.print(
                "\nInterrupted. Press Ctrl+C again within 3s to exit.",
                style=COLORS["warning"],
            )
            continue
        except ExecutionTimeoutError as exc:
            # Catch timeout errors that might propagate to the main loop
            ctx.console.print(
                "[bold]Execution Timeout:[/bold]\n"
                f"Operation exceeded maximum allowed time ({exc.max_execution_time:.2f}s).\n"
                "Please try again with a simpler task or contact support if the issue persists.",
                style=COLORS["warning"],
            )
            logger.error(
                "Unhandled execution timeout in main loop: %.2fs / %.2fs",
                exc.elapsed_time,
                exc.max_execution_time,
            )
        except Exception as exc:  # pragma: no cover - runtime safeguard
            ctx.console.print(f"[bold]Error:[/bold] {escape(str(exc))}", style=COLORS["error"])


async def _handle_conversation(ctx: AppState, query: str) -> None:
    adapter = get_adapter(ctx.current_engine)
    try:
        await adapter.handle_query(ctx, query)
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Allow interrupt to propagate to main loop for double Ctrl+C handling
        raise
    except ExecutionTimeoutError as exc:
        # Handle execution timeout specifically with detailed message
        ctx.console.print(
            "[bold]Execution Timeout:[/bold]\n"
            "The agent execution exceeded the maximum allowed time.\n"
            f"Elapsed: {exc.elapsed_time:.2f}s / Max: {exc.max_execution_time:.2f}s\n"
            "Consider breaking down your task into smaller parts or adjusting the timeout limit.",
            style=COLORS["warning"],
        )
        logger.warning(
            "Agent execution timed out: %.2fs / %.2fs",
            exc.elapsed_time,
            exc.max_execution_time,
        )
    except Exception as exc:
        ctx.console.print(f"[bold]Conversation error:[/bold] {exc}", style=COLORS["error"])


def _handle_command_result(ctx: AppState, command_name: str, result) -> bool:
    if result.type == "exit":
        ctx.console.print(result.message or "Goodbye!")
        return True

    if result.type == "error":
        ctx.console.print(result.message, style=COLORS["error"])
        if result.payload:
            _render_payload(ctx, result.payload)
        return False

    if result.type == "success":
        if result.payload:
            _render_payload(ctx, result.payload)
        if result.message:
            ctx.console.print(result.message, style=COLORS["success"])
        return False

    if result.type == "info":
        if result.message:
            ctx.console.print(result.message, style=COLORS["info"])
        if result.payload:
            _render_payload(ctx, result.payload)
        return False

    if result.type == "render":
        _render_payload(ctx, result.payload or {})
        if result.message:
            ctx.console.print(result.message)

    return False


def _render_payload(ctx: AppState, payload: Optional[dict]) -> None:
    if not payload:
        return
    kind = payload.get("kind")
    if kind == "help":
        gui_render.print_help(ctx.console, dify_mode=(ctx.current_engine == "dify"))
        return
    if kind == "info":
        data = payload.get("data", {})
        gui_render.render_info(
            ctx.console,
            data.get("agent", {}),
            data.get("mode", {}),
        )
        return
    if kind == "llm_catalog":
        gui_render.render_llms(ctx.console, payload.get("catalog", {}))
        return
    if kind == "sessions":
        sessions = payload.get("sessions", [])
        current = payload.get("current_session_id")
        formatted = gui_formatter.format_session_list(sessions, current)
        gui_render.render_sessions(ctx.console, formatted, current)
        return
    if kind == "tools_summary":
        gui_render.render_tools_summary(ctx.console, payload)
        return
    if kind == "tools_list":
        gui_render.render_tools_list(ctx.console, payload)
        return

    if "agent" in payload and "mode" in payload:
        gui_render.render_info(ctx.console, payload["agent"], payload["mode"])


def _build_prompt(ctx: AppState) -> str:
    engine = ctx.current_engine
    if engine == "agent":
        config = ctx.get_engine_config("agent")
        agent_type = config.get("agent_type", "basic")
        streaming = bool(config.get("streaming", True))
        stream_indicator = "[S]" if streaming else ""
        return (
            f"\n[{COLORS['info']}][bold]{engine}:{agent_type.upper()}{stream_indicator}"
            f"[/bold][/{COLORS['info']}] > "
        )
    if engine == "llm":
        config = ctx.get_engine_config("llm")
        streaming = bool(config.get("streaming", True))
        stream_indicator = "[S]" if streaming else ""
        return (
            f"\n[{COLORS['info']}][bold]{engine}:LLM{stream_indicator}"
            f"[/bold][/{COLORS['info']}] > "
        )
    return f"\n[{COLORS['info']}][bold]{engine}[/bold][/{COLORS['info']}] > "


def _handle_service_result(ctx: AppState, result: dict) -> bool:
    if result["type"] == "error":
        ctx.console.print(
            f"[bold]{result.get('message', 'Service initialization failed.')}[/bold]",
            style=COLORS["error"],
        )
        return False
    payload = result.get("payload", {})
    if payload:
        gui_render.render_info(
            ctx.console,
            payload.get("agent", {}),
            payload.get("mode", {}),
        )
    return True

async def _cleanup_engines(ctx: AppState) -> None:
    """Release resources for engines that maintain external connections."""
    try:
        from src.application.services.dify import DifyService

        await DifyService().cleanup(ctx)
    except Exception as exc:  # pragma: no cover - best effort cleanup
        logger.debug("Engine cleanup skipped: %s", exc)

