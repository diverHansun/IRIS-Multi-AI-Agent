"""
Rendering helpers extracted from the legacy CLI GUI module.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def print_welcome(console: Console) -> None:
    """
    Display the welcome banner with feature overview.
    """
    welcome_text = """
Multi-LLM AI Agent

Supported Features:
- Multi-LLM Support (Zhipu AI GLM-4-plus/GLM-4.5, OpenAI GPT-4o/4o-mini, Ollama local models)
- Smart conversations and complex reasoning
- Math calculations, web search, map navigation, cryptocurrency prices
- Session memory and multi-turn dialogues

Basic Commands:
/exit or /quit - Exit the program
/help - View help information
/info - View system status
/llms - View available LLM list
/model <provider> [model] - Switch LLM
/reload - Reload LLM configuration from JSON files

Working Modes:
/mode llm - LLM mode (streaming output, fast response)
/mode agent - Agent mode (tool calling, reasoning analysis)
/stream on/off - Control streaming output

Memory Management:
/clear - Clear current session memory
/new - Create new session
/sessions - View session history list
/restore <session_id> - Restore specified session
/delete_session <session_id> - Delete specified session and its files
/cleanup - Clean up sessions (remove orphaned files and indexes)

MCP Management:
/mcp status [-v] - View MCP status/servers/tool count
/mcp tools [--json] - List MCP tools (prefixed with mcp_)
/mcp reload - Reload config/mcp/mcp.toml

Connector Management:
/connector status [-v] - View connector service status
/connector tools [--json] - List available connector tools
/connector reload - Reload connector tools and refresh connections

Note: MCP tools in Agent mode are prefixed with mcp_ and require JSON object parameters.
    """
    console.print(Panel(welcome_text, title="Welcome", border_style="cyan"))


def print_help(console: Console, dify_mode: bool = False) -> None:
    """
    Display contextual help content.
    """
    if dify_mode:
        help_text = """
Dify Mode - Cloud AI Platform

File Upload & Analysis:
"/upload" - Upload files (documents, images) for AI analysis (one-time use)
"这个文件说了什么？" - Ask about uploaded file content
"分析这个图片" - Analyze uploaded images

File Management:
- Files are used once in the next conversation, then automatically cleared
- Use "/files" to see pending files
- Use "/clearfiles" to clear without using

Cloud AI Features:
- Streaming conversation with cloud AI
- File upload and analysis
- Multi-modal understanding
- Built-in conversation memory

Available Commands:

File Management:
/upload              - Upload files (support multi-select dialog or command line)
                       Example: /upload file1.pdf file2.png
/files               - List all pending files with details
/files remove <#>    - Remove specific file(s) by index number
                       Example: /files remove 2
                       Example: /files remove 1 3 5
/files clear         - Clear all pending files without using them

Conversation:
/reset               - Reset conversation (clear memory and files)
/reconnect           - Reconnect to Dify service (force reinitialize)
/info                - Show Dify connection status and file list

Mode Switch:
/switch <provider>   - Exit Dify mode and switch to local LLM
                       Example: /switch openai gpt-4o-mini

File Support:
- Documents: .txt, .md, .pdf, .docx, .xlsx, .csv, .html, .xml, .epub
- Images: .jpg, .jpeg, .png, .gif, .webp, .svg
- Max file size: 10MB per file

Note: Dify mode is a standalone cloud AI service.
Use '/switch <provider>' to exit and return to local LLM modes.
        """
    else:
        help_text = """
Usage Examples:

Math Calculations:
"Calculate 125 + 375", "Help me calculate 15 * 23 + 100"

Web Search:
"Search for latest AI news", "Find Python tutorials"

Map Navigation:
"Search for Starbucks in Beijing", "Plan walking route from Tiananmen to Forbidden City"

Cryptocurrency:
"Get current Bitcoin price", "Analyze Bitcoin price trend"

Notion Knowledge Management:
"Search for project documents in Notion", "Get recent work records from Notion"

Multi LLM Provider Switching Examples:
"/switch zhipu glm-4-plus", "/switch openai gpt-4o", "/switch ollama gpt-oss:20b", "/switch dify"

Working Modes:
/mode llm - LLM mode: fast conversation, supports streaming output (default)
/mode agent - Agent mode: full functionality, tool calling, session memory
/switch dify - Dify mode (cloud agent): cloud AI platform, file upload, streaming chat

Streaming Output:
- Only available in LLM mode
- '/stream on/off' to enable/disable

Agent Mode Available Tools:
- Math calculations, web search, map navigation, cryptocurrency prices
- Try related questions directly for detailed functionality

Basic Commands:
Type command name to view specific instructions (e.g., type '/llms' to view model list)
/reload - Reload LLM configuration from JSON files

Session Management Commands:
/clear - Clear current session memory content (keep session files)
/new - Create new session
/sessions - View session history list
/restore <session_id> - Restore specified session
/delete_session <session_id> - Delete specified session and its files
/cleanup - Clean up sessions (remove orphaned files and indexes)

MCP Usage and Commands:
- Management: /mcp status [-v] | /mcp tools [--json] | /mcp reload
        """

    console.print(Panel(help_text, title="Help Information", border_style="green"))


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

    info_text = f"""
Provider: {provider}
Model: {model}
Tool Count: {tool_count}
Mode: {mode.upper()}
Streaming: {"Enabled" if streaming else "Disabled"}
Session ID: {session_id}
    """
    console.print(Panel(info_text, title="System Information", border_style="blue"))


def render_llms(console: Console, catalog: Mapping[str, Any]) -> None:
    """
    Render available LLM providers and models.
    """
    if "error" in catalog:
        console.print(f"[red]{catalog['error']}[/]")
        if "message" in catalog:
            console.print(f"[yellow]{catalog['message']}[/]")
        return

    panel_lines: list[str] = ["Available LLM Providers:\n"]
    for provider in catalog.get("providers", []):
        panel_lines.append(f"- {provider['name']} ({provider['provider']})")
        panel_lines.append(f"  Default Model: {provider.get('default_model') or 'None'}")
        if provider.get("provider") == "ollama":
            local_models: Sequence[str] = provider.get("local_models", [])
            if local_models:
                panel_lines.append(f"  Available Models: {', '.join(local_models)}")
            elif provider.get("message"):
                panel_lines.append(f"  Note: {provider['message']}")
            if provider.get("error"):
                panel_lines.append(f"  Error: {provider['error']}")
        else:
            models_detail = provider.get("models_detail", [])
            if models_detail:
                panel_lines.append("  Supported Models:")
                for entry in models_detail:
                    tag = " [Recommended]" if entry.get("recommended") else ""
                    description = entry.get("description", "")
                    panel_lines.append(f"    * {entry.get('model')}{tag}: {description}")
        panel_lines.append("")

    recommended = catalog.get("recommended", [])
    if recommended:
        panel_lines.append("Recommended Configurations:")
        for rec in recommended:
            panel_lines.append(f"  * {rec['provider_name']} {rec['model']}: {rec['description']}")
        panel_lines.append("")

    default_cfg = catalog.get("default", {})
    if default_cfg:
        panel_lines.append(
            f"Startup Default LLM: {default_cfg.get('provider', 'N/A')} / {default_cfg.get('model', 'N/A')}"
        )

    console.print(Panel("\n".join(panel_lines), title="LLM Catalog", border_style="magenta"))


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
