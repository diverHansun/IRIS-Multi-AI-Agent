"""Rendering helpers for the refactored CLI."""

from __future__ import annotations

from textwrap import dedent
from typing import Any, Iterable, List, Mapping, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

GLOBAL_COMMANDS = [
    ("/switch <engine>", "Switch execution engine (llm | agent | agentflow | dify)"),
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

LLM_ENGINE_COMMANDS = [
    ("/model <provider> <model>", "Switch provider/model for the LLM engine"),
    ("/stream on|off", "Enable or disable LLM streaming output"),
    ("/llms", "Show the available LLM model catalog"),
    ("/reload", "Reload LLM provider configuration"),
]

AGENT_ENGINE_COMMANDS = [
    ("/switch agent", "Switch to the agent engine"),
    ("/mode basic|deep", "Toggle agent mode"),
]

BASIC_AGENT_COMMANDS = [
    ("/model <provider> <model>", "Switch provider/model for the basic agent"),
]
DEEP_AGENT_COMMANDS = [
    ("/use <function>", "Select deep agent function (research|coding|analysis)"),
    ("/deep status", "Show active deep agent details"),
    ("/deep filesystem <mode>", "Adjust filesystem middleware permissions (read-only|ask-before-edit|auto-edit)"),
    ("/deep subagents <list|status>", "Inspect available or active subagents"),
    ("/deep middleware status", "View middleware configuration summary"),
    ("/deep config <show|reload>", "Inspect or reload deep agent configuration"),
]

AGENT_TOOL_COMMANDS = [
    ("/tools [--list]", "Display available tools (summary or detailed table)"),
    ("/mcp status [-v]", "Inspect MCP servers and registered tools"),
    ("/mcp tools [--json]", "List MCP tools (prefixed with mcp_)"),
    ("/mcp reload", "Reload MCP configuration"),
    ("/connector status [-v]", "Check connector service status"),
    ("/connector tools [--json]", "List connector tools"),
    ("/connector reload", "Reload connector definitions"),
]

DIFY_FILE_COMMANDS = [
    ("/upload <paths...>", "Upload files (dialog opens when no path is provided)"),
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
        - Unified CLI for LLM, Agent, AgentFlow, and Dify engines
        - Session memory, tool orchestration, and streaming output
        - Built-in management commands for switching engines and administering sessions
        """
    ).strip()

    sections = [
        _format_command_section("Global Commands", GLOBAL_COMMANDS),
        _format_command_section("Session Management", SESSION_COMMANDS),
        _format_command_section("LLM Engine", LLM_ENGINE_COMMANDS),
        _format_command_section("Agent Engine", AGENT_ENGINE_COMMANDS),
        _format_command_section("Basic Agent Commands", BASIC_AGENT_COMMANDS),
        _format_command_section("Deep Agent Commands", DEEP_AGENT_COMMANDS),
        _format_command_section("Agent Tools", AGENT_TOOL_COMMANDS),
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
            _format_command_section("File Management", DIFY_FILE_COMMANDS),
            _format_command_section(
                "Conversation Management", DIFY_CONVERSATION_COMMANDS
            ),
        ]

        tips = dedent(
            """
            Tips:
            - Files are queued after upload and sent with the next query
            - `files remove` uses 1-based indices (shown in `/files` output)
            - For complex workflows, use `/switch agent` to access full agent capabilities
            """
        ).strip()

        body = "\n\n".join(dify_sections) + f"\n\n{tips}"
        console.print(Panel(body, title="Dify Mode Help", border_style="green"))
        return

    sections = [
        _format_command_section("Global Commands", GLOBAL_COMMANDS),
        _format_command_section("Session Management", SESSION_COMMANDS),
        _format_command_section("LLM Engine", LLM_ENGINE_COMMANDS),
        _format_command_section("Agent Engine", AGENT_ENGINE_COMMANDS),
        _format_command_section("Basic Agent Commands", BASIC_AGENT_COMMANDS),
        _format_command_section("Deep Agent Commands", DEEP_AGENT_COMMANDS),
        _format_command_section("Agent Tools", AGENT_TOOL_COMMANDS),
    ]

    examples = dedent(
        """
        Examples:
        - /switch agent               Switch to the Agent engine
        - /mode basic                 Use the basic agent mode
        - /model openai gpt-4o        Switch provider and model
        - /use coding                 Activate coding deep-agent function
        - /deep status                Inspect deep agent configuration
        - /stream on                  Enable LLM streaming output
        - /switch dify                Switch to the Dify engine
        """
    ).strip()

    body = "\n\n".join(sections) + f"\n\n{examples}"
    console.print(Panel(body, title="Help", border_style="green"))


def render_info(
    console: Console, agent_info: Mapping[str, Any], mode_info: Mapping[str, Any]
) -> None:
    """
    Render system information including agent details and mode state.
    """

    provider = agent_info.get("provider", "unknown")
    model = agent_info.get("model", "unknown")
    tool_count = agent_info.get("tool_count", 0)
    streaming = mode_info.get("streaming", True)
    mode = mode_info.get("mode", "llm")
    session_id = mode_info.get("session_id", "N/A")
    agent_type = mode_info.get("agent_type")
    function_type = mode_info.get("function_type") or agent_info.get("function_type")
    middleware_info = mode_info.get("middleware") or agent_info.get("middleware")
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

    if agent_type:
        lines.append(f"Agent Type: {agent_type}")
    if agent_type == "deep":
        lines.append(f"Deep Function: {function_type or 'N/A'}")
        if middleware_info:
            if isinstance(middleware_info, dict):
                middleware_summary = ", ".join(sorted(middleware_info.keys()))
            elif isinstance(middleware_info, list):
                middleware_summary = ", ".join(middleware_info)
            else:
                middleware_summary = str(middleware_info)
            lines.append(f"Middleware: {middleware_summary or 'N/A'}")

    if conversation_id:
        lines.append(f"Conversation ID: {conversation_id}")
    if files_count is not None:
        lines.append(f"Queued Files: {files_count}")

    console.print(
        Panel("\n".join(lines), title="System Information", border_style="blue")
    )


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
            raw_models = provider.get("models_detail") or []
            models_detail = raw_models.values() if isinstance(raw_models, dict) else raw_models
            models_detail = list(models_detail)
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
            lines.append(
                f"  * {rec['provider_name']} {rec['model']}: {rec['description']}"
            )
        lines.append("")

    default_cfg = catalog.get("default", {})
    if default_cfg:
        lines.append(
            f"Startup Default LLM: {default_cfg.get('provider', 'N/A')} / {default_cfg.get('model', 'N/A')}"
        )

    console.print(Panel("\n".join(lines), title="LLM Catalog", border_style="magenta"))


def render_sessions(
    console: Console,
    sessions: Iterable[Mapping[str, Any]],
    current_session_id: str | None,
) -> None:
    """
    Render session list using a table layout.
    """

    table = Table(title="Sessions")
    table.add_column("Active", style="cyan", justify="center", width=8)
    table.add_column("Session ID", style="green", no_wrap=True)
    table.add_column("Messages", style="magenta", justify="right", width=10)
    table.add_column("Created At", style="yellow", no_wrap=True)
    table.add_column("Updated At", style="yellow", no_wrap=True)

    for session in sessions:
        session_id = session.get("session_id", session.get("id", ""))
        message_count = session.get("message_count", 0)
        created_at = session.get("created_at", "")
        updated_at = session.get("updated_at", "")
        
        # Format timestamps for better readability
        if created_at and "T" in created_at:
            created_at = created_at.split("T")[0] + " " + created_at.split("T")[1][:8]
        if updated_at and "T" in updated_at:
            updated_at = updated_at.split("T")[0] + " " + updated_at.split("T")[1][:8]
        
        active_marker = "*" if session_id == current_session_id else ""
        table.add_row(active_marker, session_id, str(message_count), created_at, updated_at)

    console.print(table)


def render_mcp_status(
    console: Console, status: Mapping[str, Any], verbose: bool = False
) -> None:
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


def render_mcp_tools(
    console: Console, tools: Iterable[Any], json_flag: bool = False
) -> None:
    """
    Render MCP tool information.
    """

    if json_flag:
        serialised = [
            {
                "name": getattr(tool, "name", "unknown"),
                "description": getattr(tool, "description", "") or "",
            }
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


def render_connector_status(
    console: Console, status: Mapping[str, Any], verbose: bool = False
) -> None:
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

    console.print(
        Panel("\n".join(lines), title="Connector Status", border_style="cyan")
    )


def render_connector_tools(
    console: Console, tools: Mapping[str, str], json_flag: bool = False
) -> None:
    """
    Render connector tool list.
    """

    if json_flag:
        serialised = [
            {"name": name, "description": description}
            for name, description in tools.items()
        ]
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


def render_tools_summary(console: Console, payload: Mapping[str, Any]) -> None:
    """
    Render unified tool summary view.
    """

    total = payload.get("total", 0)
    providers = payload.get("providers", [])

    lines: List[str] = [f"Available Tools ({total} total):"]

    for provider in providers:
        display_name = provider.get("display_name", "Unknown")
        count = provider.get("count", 0)
        samples = provider.get("samples", [])
        warning = provider.get("warning")

        if samples:
            sample_text = ", ".join(samples)
        elif count:
            sample_text = "No sample tools available."
        else:
            sample_text = "No tools available."

        lines.append(f"{display_name} ({count}): {sample_text}")

        if warning:
            lines.append(f"  ! {warning}")

    console.print(Panel("\n".join(lines), title="Tool Summary", border_style="blue"))


def render_tools_list(console: Console, payload: Mapping[str, Any]) -> None:
    """
    Render detailed tool table.
    """

    tools = payload.get("tools", [])
    warnings = payload.get("warnings", [])
    total = payload.get("total", len(tools))

    if not tools:
        console.print(Panel("No tools available.", title="Tool List", border_style="blue"))
    else:
        table = Table(title=f"Tool List ({total})", show_lines=False)
        table.add_column("Tool Name", justify="left")
        table.add_column("Provider", justify="left")
        table.add_column("Description", justify="left")

        for entry in tools:
            table.add_row(
                entry.get("name", "unknown"),
                entry.get("provider", "unknown"),
                entry.get("description", ""),
            )

        console.print(table)

    for warning in warnings:
        console.print(f"[yellow]{warning}[/]")
