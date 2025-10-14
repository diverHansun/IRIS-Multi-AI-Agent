"""Rendering helpers for the refactored CLI."""

from __future__ import annotations

from textwrap import dedent
from typing import Any, Iterable, Mapping, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

GLOBAL_COMMANDS = [
    ("/switch <engine>", "Switch execution engine (langchain | langgraph | dify)"),
    ("/help", "Show contextual help"),
    ("/info", "Display current engine status"),
    ("/exit", "Exit the application"),
]

SESSION_COMMANDS = [
    ("/new", "Create a fresh session"),
    ("/clear", "Clear the messages for the active session"),
    ("/sessions", "List stored sessions"),
    ("/restore <session_id>", "Restore session by ID"),
    ("/delete_session <session_id>", "Delete a session and its files"),
    ("/cleanup", "Remove orphaned session data"),
]

LANGCHAIN_CORE_COMMANDS = [
    ("/model <provider> [model]", "Switch model used by LangChain"),
    ("/mode llm|agent", "Toggle between LLM and Agent modes"),
    ("/stream on|off", "Enable or disable streaming output"),
    ("/llms", "Show the available model catalog"),
    ("/reload", "Reload provider configuration"),
]

LANGCHAIN_TOOL_COMMANDS = [
    ("/mcp status [-v]", "Inspect MCP servers and registered tools"),
    ("/mcp tools [--json]", "List MCP tools (prefixed with mcp_)"),
    ("/mcp reload", "Reload MCP configuration"),
    ("/connector status [-v]", "Check connector service status"),
    ("/connector tools [--json]", "List connector tools"),
    ("/connector reload", "Reload connector definitions"),
]

DIFY_FILE_COMMANDS = [
    ("/upload [paths...]", "Upload files (dialog opens when no path is provided)"),
    ("/files", "List files queued for the next conversation"),
    ("/files remove <index ...>", "Remove files by 1-based index"),
    ("/files clear", "Clear queued files without using them"),
]

DIFY_CONVERSATION_COMMANDS = [
    ("/reset", "Reset the current Dify conversation"),
    ("/reconnect", "Re-initialise the Dify client"),
    ("/info", "Show Dify connection status"),
]


def _format_command_section(title: str, commands: Sequence[tuple[str, str]]) -> str:
    lines = [title, "-" * len(title)]
    for syntax, description in commands:
        lines.append(f"{syntax:<28} {description}")
    return "\n".join(lines)


def print_welcome(console: Console) -> None:
    """
    Display the welcome banner with key capabilities and command overview.
    """

    summary = dedent(
        """
        Multi-Engine AI Assistant

        Highlights:
        - Unified CLI for LangChain (local), Dify (cloud), and LangGraph (reserved) engines
        - Session memory, tool orchestration, and streaming output
        - Built-in management commands for switching engines and administering sessions
        """
    ).strip()

    sections = [
        _format_command_section("Global Commands", GLOBAL_COMMANDS),
        _format_command_section("Session Management", SESSION_COMMANDS),
        _format_command_section("LangChain Core", LANGCHAIN_CORE_COMMANDS),
        _format_command_section("Tool Management", LANGCHAIN_TOOL_COMMANDS),
    ]

    body = summary + "\n\n" + "\n\n".join(sections)
    console.print(Panel(body, title="Welcome", border_style="cyan"))


def print_help(console: Console, dify_mode: bool = False) -> None:
    """
    Display contextual help content.
    """

    if dify_mode:
        dify_sections = [
            _format_command_section("Global Commands", GLOBAL_COMMANDS),
            _format_command_section("文件管理", DIFY_FILE_COMMANDS),
            _format_command_section("会话控制", DIFY_CONVERSATION_COMMANDS),
        ]

        tips = dedent(
            """
            提示:
            - 上传的文件只在下一次对话中消费一次，发送后会自动清空。
            - `files remove` 使用 1-based 序号，可一次移除多个文件。
            - 如需返回本地引擎，请执行 `/switch langchain` 或其它目标引擎。
            """
        ).strip()

        body = "\n\n".join(dify_sections) + f"\n\n{tips}"
        console.print(Panel(body, title="Dify Mode Help", border_style="cyan"))
        return

    sections = [
        _format_command_section("Global Commands", GLOBAL_COMMANDS),
        _format_command_section("Session Management", SESSION_COMMANDS),
        _format_command_section("LangChain Core", LANGCHAIN_CORE_COMMANDS),
        _format_command_section("Tool Management", LANGCHAIN_TOOL_COMMANDS),
    ]

    examples = dedent(
        """
        Examples:
        - /switch langchain            切换回 LangChain 引擎
        - /model openai gpt-4o         调整到指定模型
        - /mode agent                  进入 Agent 模式，支持工具调用
        - /stream on                   启用流式输出
        - /switch dify                 进入 Dify 模式
        """
    ).strip()

    body = "\n\n".join(sections) + f"\n\n{examples}"
    console.print(Panel(body, title="Help", border_style="green"))


def render_info(console: Console, agent_info: Mapping[str, Any], mode_info: Mapping[str, Any]) -> None:
    """
    Render system information including agent details and mode state.
    """

    provider = agent_info.get("provider", "unknown")
    model = agent_info.get("model", "unknown")
    tool_count = agent_info.get("tool_count", 0)
    streaming = mode_info.get("streaming", True)
    mode = mode_info.get("mode", "llm")
    session_id = mode_info.get("session_id", "N/A")
    conversation_id = agent_info.get("conversation_id")
    files_count = agent_info.get("files_count")

    lines = [
        f"Provider: {provider}",
        f"Model: {model}",
        f"Tool Count: {tool_count}",
        f"Mode: {mode.upper()}",
        f"Streaming: {'Enabled' if streaming else 'Disabled'}",
        f"Session ID: {session_id}",
    ]

    if conversation_id:
        lines.append(f"Conversation ID: {conversation_id}")
    if files_count is not None:
        lines.append(f"Queued Files: {files_count}")

    console.print(Panel("\n".join(lines), title="System Information", border_style="blue"))


def render_llms(console: Console, catalog: Mapping[str, Any]) -> None:
    """
    Render available LLM providers and models.
    """

    if "error" in catalog:
        console.print(f"[red]{catalog['error']}[/]")
        if "message" in catalog:
            console.print(f"[yellow]{catalog['message']}[/]")
        return

    lines: list[str] = ["Available LLM Providers:\n"]
    for provider in catalog.get("providers", []):
        lines.append(f"- {provider['name']} ({provider['provider']})")
        lines.append(f"  Default Model: {provider.get('default_model') or 'None'}")
        if provider.get("provider") == "ollama":
            local_models: Sequence[str] = provider.get("local_models", [])
            if local_models:
                lines.append(f"  Available Models: {', '.join(local_models)}")
            elif provider.get("message"):
                lines.append(f"  Note: {provider['message']}")
            if provider.get("error"):
                lines.append(f"  Error: {provider['error']}")
        else:
            models_detail = provider.get("models_detail", [])
            if models_detail:
                lines.append("  Supported Models:")
                for entry in models_detail:
                    tag = " [Recommended]" if entry.get("recommended") else ""
                    description = entry.get("description", "")
                    lines.append(f"    * {entry.get('model')}{tag}: {description}")
        lines.append("")

    recommended = catalog.get("recommended", [])
    if recommended:
        lines.append("Recommended Configurations:")
        for rec in recommended:
            lines.append(f"  * {rec['provider_name']} {rec['model']}: {rec['description']}")
        lines.append("")

    default_cfg = catalog.get("default", {})
    if default_cfg:
        lines.append(
            f"Startup Default LLM: {default_cfg.get('provider', 'N/A')} / {default_cfg.get('model', 'N/A')}"
        )

    console.print(Panel("\n".join(lines), title="LLM Catalog", border_style="magenta"))


def render_sessions(console: Console, sessions: Iterable[Mapping[str, Any]], current_session_id: str | None) -> None:
    """
    Render session list using a table layout.
    """

    table = Table(title="Sessions")
    table.add_column("Active", style="cyan", justify="center")
    table.add_column("Session ID", style="green")
    table.add_column("Created At", style="yellow")
    table.add_column("Notes", style="white")

    for session in sessions:
        session_id = session.get("id", "")
        created_at = session.get("created_at_display", session.get("created_at", ""))
        notes = session.get("notes", "")
        active_marker = "*" if session_id == current_session_id else ""
        table.add_row(active_marker, session_id, created_at, notes)

    console.print(table)


def render_mcp_status(console: Console, status: Mapping[str, Any], verbose: bool = False) -> None:
    """
    Render the MCP status payload.
    """

    if verbose:
        console.print_json(data=status)
        return

    if not status:
        console.print("[yellow]No MCP status information available.[/]")
        return

    lines = [
        f"Enabled: {status.get('enabled')}  Initialized: {status.get('initialized')}",
        f"Tool Count: {status.get('tools_total', 0)}",
        f"Config Path: {status.get('config_path') or 'N/A'}",
        f"Last Reload: {status.get('last_reload') or 'N/A'}",
    ]
    for server in status.get("servers", []):
        lines.append(
            f"- {server.get('name', 'unknown')}: {server.get('status', 'unknown')} "
            f"(tools: {server.get('tools_count')})"
        )
    if status.get("last_error"):
        lines.append(f"Last Error: {status['last_error']}")

    console.print(Panel("\n".join(lines), title="MCP Status", border_style="magenta"))


def render_mcp_tools(console: Console, tools: Iterable[Any], json_flag: bool = False) -> None:
    """
    Render MCP tool information.
    """

    if json_flag:
        serialised = [
            {"name": getattr(tool, "name", "unknown"), "description": getattr(tool, "description", "") or ""}
            for tool in tools
        ]
        console.print_json(data=serialised)
        return

    tool_list = list(tools)
    if not tool_list:
        console.print("[yellow]No MCP tools available.[/]")
        return

    lines = [f"Total {len(tool_list)} MCP tool(s):"]
    for tool in tool_list[:100]:
        description = getattr(tool, "description", "") or ""
        lines.append(f"- {getattr(tool, 'name', 'unknown')}: {description[:120]}")
    if len(tool_list) > 100:
        lines.append(f"... {len(tool_list) - 100} more tool(s) not shown")

    console.print(Panel("\n".join(lines), title="MCP Tools", border_style="magenta"))


def render_connector_status(console: Console, status: Mapping[str, Any], verbose: bool = False) -> None:
    """
    Render connector service status.
    """

    if verbose:
        console.print_json(data=status)
        return

    if not status:
        console.print("[yellow]No connector status information available.[/]")
        return

    lines = [
        f"Service: {status.get('service', 'N/A')}  Status: {status.get('status', 'unknown')}",
        f"Tool Count: {status.get('tool_count', 0)}",
        f"Base URL: {status.get('base_url', 'N/A')}",
        f"Timeout: {status.get('timeout', 'N/A')}s  Stream Timeout: {status.get('stream_timeout', 'N/A')}s",
    ]
    if status.get("schema_error"):
        lines.append(f"Schema Error: {status['schema_error']}")

    console.print(Panel("\n".join(lines), title="Connector Status", border_style="cyan"))


def render_connector_tools(console: Console, tools: Mapping[str, str], json_flag: bool = False) -> None:
    """
    Render connector tool list.
    """

    if json_flag:
        serialised = [{"name": name, "description": description} for name, description in tools.items()]
        console.print_json(data=serialised)
        return

    if not tools:
        console.print("[yellow]No connector tools registered.[/]")
        return

    lines = [f"Total {len(tools)} connector tool(s):"]
    for name, description in list(tools.items())[:100]:
        lines.append(f"- {name}: {description[:120]}")
    if len(tools) > 100:
        lines.append(f"... {len(tools) - 100} more tool(s) not shown")

    console.print(Panel("\n".join(lines), title="Connector Tools", border_style="cyan"))

