"""
GUI module for the Multi-AI-Agent project.
This module contains Rich-based rendering functions.
"""

from rich.panel import Panel


def print_welcome(console):
    """Print welcome message in English"""
    welcome_text = """
Multi-LLM AI Agent 

Supported Features:
• Multi-LLM Support (Zhipu AI GLM-4-plus/GLM-4.5, OpenAI GPT-4o/4o-mini, Ollama Local Models)
• Smart Conversations and Complex Reasoning
• Math Calculations, Web Search, Map Navigation, Cryptocurrency Prices
• Session Memory and Multi-turn Dialogues

Basic Commands:
/exit or /quit - Exit the program
/help - View help information
/info - View system status
/llms - View available LLM list
/switch <provider> [model] - Switch LLM
/reload - Reload LLM configuration from JSON files

Working Modes:
/mode llm - LLM Mode (Streaming output, fast response)
/mode agent - Agent Mode (Tool calling, reasoning analysis)
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

Note: MCP tools in Agent mode are prefixed with mcp_ and require JSON object parameters
    """
    console.print(Panel(welcome_text, title="Welcome", border_style="cyan"))


def print_help(console, dify_mode=False):
    """Print help message in English"""
    if dify_mode:
        help_text = """
Dify Mode - Cloud AI Platform:

File Upload & Analysis:
"/upload" - Upload files (documents, images) for AI analysis (one-time use)
"这个文件说了什么？" - Ask about uploaded file content
"分析这个图片" - Analyze uploaded images

File Management:
• Files are used ONCE in the next conversation, then automatically cleared
• Use "/files" to see pending files • Use "/clearfiles" to clear without using

Cloud AI Features:
• Streaming conversation with cloud AI
• File upload and analysis
• Multi-modal understanding
• Built-in conversation memory

Available Commands:
• /upload - Upload files for analysis (files are used once in next conversation)
• /files - List currently pending files for next conversation
• /clearfiles - Clear pending files without using them
• /reset - Reset conversation (clear memory)
• /reconnect - Reconnect to Dify service (force reinitialize connection)
• /info - Show Dify connection status and uploaded files
• /switch dify - Exit Dify mode and return to local LLM modes

File Support:
• Documents: .txt, .md, .pdf, .docx, .xlsx, .csv, .html, .xml, .epub
• Images: .jpg, .jpeg, .png, .gif, .webp, .svg
• Max file size: 10MB per file

Note: Dify mode is a standalone cloud AI service. 
Use 'switch dify' to exit and return to local LLM modes.
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
• LLM Mode: Fast conversation, supports streaming output (default)
• Agent Mode: Full functionality, tool calling, session memory
• Dify Mode(Cloud Agent): Cloud AI platform, file upload, streaming chat

Streaming Output:
• Only available in LLM mode
• '/stream on/off' to enable/disable

Available Tools:
• Math calculations, web search, map navigation, cryptocurrency prices
• Dify: File upload (/upload), conversation reset (/reset)
• Try related questions directly for detailed functionality

Basic Commands:
Type command name to view specific instructions (e.g., type '/llms' to view model list)
/reload - Reload LLM configuration from JSON files 

Session Management Commands:
• /clear - Clear current session memory content (keep session files)
• /new - Create new session
• /sessions - View session history list
• /restore <session_id> - Restore specified session
• /delete_session <session_id> - Delete specified session and its files
• /cleanup - Clean up sessions (remove orphaned files and indexes)
        """
    
    # Append MCP instruction description (only for non-Dify modes)
    if not dify_mode:
        help_text += "\nMCP Usage and Commands:\n"
        help_text += "- Management: /mcp status [-v] | /mcp tools [--json] | /mcp reload\n"
        help_text += "- In Agent mode: Tool names are prefixed with mcp_ (e.g., mcp_API-post-search); Action Input must be a single-line JSON (e.g., {\"query\":\"keyword\"}).\n"
        help_text += "  Example: Call mcp_API-post-search with parameters {\"query\":\"Roadmap\"}; Call mcp_API-retrieve-a-page with parameters {\"page_id\":\"<page_id>\"}\n"
    
    console.print(Panel(help_text, title="Help Information", border_style="green"))


def render_llms(console, catalog):
    """Render available LLMs list"""
    if "error" in catalog:
        console.print(f"[red]❌ {catalog['error']}[/]")
        console.print(f"[yellow]{catalog['message']}[/]")
        return
    
    llm_text = "Available LLM Providers:\n\n"
    
    for provider in catalog["providers"]:
        llm_text += f"- {provider['name']} ({provider['provider']})\n"
        llm_text += f"  Default Model: {provider['default_model'] or 'None'}\n"
        
        # Ollama special handling
        if provider['provider'] == 'ollama':
            if "local_models" in provider:
                if provider["local_models"]:
                    llm_text += f"  Available Models: {', '.join(provider['local_models'])}\n"
                else:
                    llm_text += "  Available Models: None\n"
                    if "message" in provider:
                        llm_text += f"  Note: {provider['message']}\n"
            if "error" in provider:
                llm_text += f"  Error: {provider['error']}\n"
        else:
            # Other providers show static supported model list
            if "models" in provider:
                llm_text += "  Supported Models:\n"
                for model, info in provider["models"].items():
                    recommended = " [Recommended]" if info.get("recommended", False) else ""
                    llm_text += f"    * {model}{recommended}: {info['description']}\n"
        
        llm_text += "\n"
    
    if catalog["recommended"]:
        llm_text += "Recommended Configurations:\n"
        for rec in catalog["recommended"]:
            llm_text += f"  * {rec['provider_name']} {rec['model']}: {rec['description']}\n"
    
    if catalog["default"]:
        llm_text += f"\nStartup Default LLM: {catalog['default'].get('provider', 'N/A')} / {catalog['default'].get('model', 'N/A')}"
    
    console.print(Panel(llm_text, title="LLM Information", border_style="blue"))


def render_info(console, agent_info, mode_info):
    """Render system information"""
    llm_info = agent_info
    
    console.print(f"[bold blue]System Information:[/]")
    console.print(f"  LLM Provider: {llm_info.get('provider', 'N/A')}")
    console.print(f"  Model: {llm_info['model']}")
    console.print(f"  Temperature: {llm_info.get('temperature', 'N/A')}")
    console.print(f"  Initialized: {llm_info['initialized']}")
    
    # Show model special information (GLM-4.5)
    if llm_info.get('thinking_mode'):
        console.print(f"  Thinking Mode: [green]Enabled[/]")
    
    # Show current mode
    mode_text = "LLM Mode (Streaming)" if mode_info["llm_mode"] else "Agent Mode (Tool Calling)"
    console.print(f"  Working Mode: {mode_text}")
    
    if mode_info["llm_mode"]:
        console.print(f"    Streaming: {'Enabled' if mode_info['streaming_enabled'] else 'Disabled'}")
        console.print(f"    Mode Features: Fast response, real-time display, no tool calling")
        # Show model special features
        if llm_info.get('model_features'):
            console.print(f"    Model Features: {', '.join(llm_info['model_features'])}")
    else:
        console.print(f"    Memory: {'Enabled' if llm_info.get('memory_enabled', False) else 'Disabled'}")
        console.print(f"    Tool Count: {llm_info['tool_count']}")
        console.print(f"    Available Tools: {', '.join(llm_info['tools'])}")
        console.print(f"    Mode Features: Full reasoning, tool calling, session memory")
        # Show model special features
        if llm_info.get('model_features'):
            console.print(f"    Model Features: {', '.join(llm_info['model_features'])}")
    
    console.print(f"  Current Session ID: {mode_info['session_id']}")


def render_dify_info(console, dify_info, session_id):
    """Render Dify system information"""
    console.print(f"[bold blue]System Information:[/]")
    console.print(f"  Provider: {dify_info['provider']}")
    console.print(f"  Model: {dify_info['model']}")
    console.print(f"  Initialized: {dify_info['initialized']}")
    
    # Show Dify-specific information
    console.print(f"  Working Mode: [cyan]Dify Mode (Cloud AI)[/]")
    console.print(f"    Base URL: [dim]{dify_info['base_url']}[/]")
    console.print(f"    API Key: [dim]{dify_info['api_key_prefix']}[/]")
    console.print(f"    Timeout: {dify_info['timeout']}s")
    
    # Show conversation information
    if dify_info['conversation_id']:
        console.print(f"    Conversation ID: [dim]{dify_info['conversation_id'][:20]}...[/]")
    else:
        console.print(f"    Conversation ID: [yellow]Not started[/]")
    
    # Show file upload information
    console.print(f"    Uploaded Files: {dify_info['uploaded_files_count']}")
    if dify_info['uploaded_files']:
        for i, file_info in enumerate(dify_info['uploaded_files'], 1):
            file_type = file_info['type']
            file_id = file_info['file_id'][:8] + "..." if len(file_info['file_id']) > 8 else file_info['file_id']
            console.print(f"      [{i}] {file_type} ({file_id})")
    
    # Show file support information
    supported_types = dify_info['supported_file_types']
    if supported_types:
        console.print(f"    Supported File Types: {', '.join(supported_types[:5])}{'...' if len(supported_types) > 5 else ''}")
    console.print(f"    Max File Size: {dify_info['max_file_size_mb']:.1f}MB")
    
    # Show mode features
    console.print(f"    Mode Features: File upload, streaming chat, cloud intelligence")
    
    console.print(f"  Current Session ID: {session_id}")


def render_sessions(console, sessions, current_session_id):
    """Render session list"""
    if sessions:
        console.print(f"[bold blue]Session History ({len(sessions)} sessions):[/]")
        for i, session in enumerate(sessions[:10], 1):  # Show first 10
            created_time = session.get("created_at", "")[:19] if session.get("created_at") else "Unknown"
            updated_time = session.get("updated_at", "")[:19] if session.get("updated_at") else "Unknown"
            current_marker = " [Current]" if session['session_id'] == current_session_id else ""
            console.print(f"  {i}. {session['session_id']}{current_marker}")
            console.print(f"      Message Count: {session['message_count']} | Created: {created_time} | Updated: {updated_time}")
        if len(sessions) > 10:
            console.print(f"  ... {len(sessions) - 10} more sessions")
        console.print("[dim]Use 'restore <session_id>' to restore a session[/]")
        console.print("[dim]Use 'delete_session <session_id>' to delete a session[/]")
    else:
        console.print("[yellow]No session history available[/]")


def render_mcp_status(console, status, verbose=False):
    """Render MCP status"""
    if verbose:
        import json
        console.print(Panel(json.dumps(status, ensure_ascii=False, indent=2), title="MCP Status", border_style="magenta"))
    else:
        servers = status.get("servers", [])
        lines = [
            f"Enabled: {status.get('enabled')}  Initialized: {status.get('initialized')}  Tool Count: {status.get('tools_total')}",
            f"Config: {status.get('config_path') or 'N/A'}  Last Reload: {status.get('last_reload') or 'N/A'}",
        ]
        for s in servers:
            lines.append(f"- {s.get('name')}: {s.get('status')} (tools: {s.get('tools_count')})")
        if status.get("last_error"):
            lines.append(f"Error: {status['last_error']}")
        console.print(Panel("\n".join(lines), title="MCP Status", border_style="magenta"))


def render_mcp_tools(console, tools, json_flag=False):
    """Render MCP tools"""
    if json_flag:
        import json
        data = [{"name": t.name, "description": getattr(t, "description", "") or ""} for t in tools]
        console.print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if tools:
            lines = [f"Total {len(tools)} MCP tools:"]
            for t in tools[:100]:
                desc = getattr(t, "description", "") or ""
                lines.append(f"- {t.name}: {desc[:120]}")
            if len(tools) > 100:
                lines.append(f"... {len(tools) - 100} more tools not shown")
            console.print(Panel("\n".join(lines), title="MCP Tools", border_style="magenta"))
        else:
            console.print("[yellow]No MCP tools available (possibly not enabled or initialization failed)[/]")