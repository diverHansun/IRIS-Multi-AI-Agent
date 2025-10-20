"""
Refactored CLI main loop entrypoint.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.components.shared.memory import GlobalMemoryManager, SessionManager

from src.application.commands import dispatch
from src.application.commands.parser import extract_command_name, is_command, parse_command
from src.application.engine_adapters import get_adapter
from src.application.services import get_current_service
from src.application.cli.gui import formatter as gui_formatter
from src.application.cli.gui import render as gui_render
from src.application.cli.gui import logo as gui_logo
from src.application.cli.state import AppState

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
    ctx.console.print("[yellow]Initializing memory system...[/]")
    ctx.global_memory = GlobalMemoryManager(storage_dir="data/sessions", max_messages=50)
    ctx.session_manager = SessionManager(ctx.global_memory)
    ctx.session_id = ctx.session_manager.prompt_for_session_choice()
    ctx.console.print(f"[dim]Current Session ID: {ctx.session_id}[/]")


async def _cli_loop(ctx: AppState) -> None:
    while True:
        try:
            prompt = _build_prompt(ctx)
            query = await asyncio.to_thread(ctx.console.input, prompt)
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
            ctx.console.print("\n[yellow]Interrupted. Cleaning up...[/]")
            ctx.console.print("Goodbye!")
            break
        except Exception as exc:  # pragma: no cover - runtime safeguard
            ctx.console.print(f"[bold red]Error: {exc}")


async def _handle_conversation(ctx: AppState, query: str) -> None:
    adapter = get_adapter(ctx.current_engine)
    try:
        await adapter.handle_query(ctx, query)
    except Exception as exc:
        ctx.console.print(f"[bold red]Conversation error: {exc}")


def _handle_command_result(ctx: AppState, command_name: str, result) -> bool:
    if result.type == "exit":
        ctx.console.print(result.message or "Goodbye!")
        return True

    if result.type == "error":
        ctx.console.print(f"[red]{result.message}[/]")
        if result.payload:
            _render_payload(ctx, result.payload)
        return False

    if result.type == "success":
        if result.payload:
            _render_payload(ctx, result.payload)
        if result.message:
            ctx.console.print(f"[green]{result.message}[/]")
        return False

    if result.type == "info":
        if result.message:
            ctx.console.print(f"[cyan]{result.message}[/]")
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
        return f"\n[bold cyan]{engine}:{agent_type.upper()}{stream_indicator}[/] > "
    if engine == "llm":
        config = ctx.get_engine_config("llm")
        streaming = bool(config.get("streaming", True))
        stream_indicator = "[S]" if streaming else ""
        return f"\n[bold cyan]{engine}:LLM{stream_indicator}[/] > "
    return f"\n[bold cyan]{engine}[/] > "


def _handle_service_result(ctx: AppState, result: dict) -> bool:
    if result["type"] == "error":
        ctx.console.print(f"[bold red]{result.get('message', 'Service initialization failed.')}[/]")
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


