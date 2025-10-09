"""
CLI module for the Multi-AI-Agent project.
This module contains the main CLI loop and command routing.
"""

import asyncio
import logging
from rich.console import Console

logger = logging.getLogger(__name__)

# Import the IRIS logo display function
from src.ui.logo.logo import display_logo,display_logo_intro

from src.agents.agent_factory import create_default_agent, get_available_configurations
from src.llm.streaming_llm import stream_llm_response
from src.memory import GlobalMemoryManager, SessionManager

# Try to import MCP manager
try:
    from src.tools.mcp import GlobalMCPManager
    MCP_AVAILABLE = True
except Exception:
    GlobalMCPManager = None
    MCP_AVAILABLE = False

# Import components
from . import control, session_control, mcp_control, registry, gui
from .connector_control import connector_status, connector_tools, connector_reload


class AppState:
    """Application state"""
    def __init__(self):
        self.console = Console()
        self.agent = None
        self.global_memory = None
        self.session_manager = None
        self.session_id = None
        self.llm_mode = True  # True: LLM mode (streaming chat), False: Agent mode (tool calling)
        self.streaming_enabled = True  # Effective only when llm_mode is True
        self.mcp_manager = GlobalMCPManager if MCP_AVAILABLE else None
        # Dify integration
        self.dify_mode = False  # Dify mode flag
        self.dify_control = None  # Dify control instance


def parse_command(query: str) -> tuple[str, str]:
    """
    Parse command, preserving / prefix for command/conversation separation

    Args:
        query: User input command

    Returns:
        (command_part, args_part) tuple
    """
    # Remove leading/trailing spaces
    query = query.strip()

    if not query:
        return "", ""

    # Keep / prefix - only remove it when dispatching to control modules
    # Split command and arguments
    parts = query.split(' ', 1)
    command = parts[0].strip() if parts else ""
    args = parts[1].strip() if len(parts) > 1 else ""

    return command, args


def is_command(query: str) -> bool:
    """
    Check if input is a command (starts with /) or conversation

    Args:
        query: User input

    Returns:
        True if command, False if conversation
    """
    return query.strip().startswith('/')


def extract_command_name(command: str) -> str:
    """
    Extract command name without / prefix for dispatching

    Args:
        command: Command with / prefix (e.g., "/switch")

    Returns:
        Command name without prefix (e.g., "switch")
    """
    if command.startswith('/'):
        return command[1:]
    return command


async def run():
    """Main CLI loop"""
    # Display the IRIS logo at startup
    display_logo()
    display_logo_intro()
    # Create app state
    ctx = AppState()
    
    # Check for at least one LLM available
    configs = get_available_configurations()
    if not configs["available_providers"]:
        ctx.console.print("[bold red]Error: No LLM providers available[/]")
        ctx.console.print("Please set at least one API key in your .env file:")
        ctx.console.print("- ZHIPU_API_KEY (Zhipu AI)")
        ctx.console.print("- OPENAI_API_KEY (OpenAI)")
        return

    # Print welcome message
    gui.print_welcome(ctx.console)

    # Initialize global memory system
    ctx.console.print("[yellow]Initializing memory system...[/]")
    ctx.global_memory = GlobalMemoryManager(storage_dir="data/sessions", max_messages=50)
    ctx.session_manager = SessionManager(ctx.global_memory)
    
    # Interactive session selection (restore or create new)
    ctx.session_id = ctx.session_manager.prompt_for_session_choice()
    ctx.console.print(f"[dim]Current Session ID: {ctx.session_id}[/]")
    
    try:
        # Create default Agent (async) and integrate global memory
        with ctx.console.status("[yellow]Initializing default Agent...[/]"):
            ctx.agent = await create_default_agent(
                verbose=True,
                temperature=0.1,
                global_memory_manager=ctx.global_memory  # Pass global memory manager
            )

        # Show initialization info
        info = ctx.agent.get_info()
        ctx.console.print(f"[green]Agent initialized successfully[/]")
        ctx.console.print(f"[dim]Provider: {info['provider']}, Model: {info['model']}, Tool Count: {info['tool_count']}[/]")
        
        # Show current mode and prompt
        if ctx.llm_mode:
            ctx.console.print(f"[green]Current Mode: LLM Mode (Streaming Output)[/]")
            ctx.console.print(f"[dim]Model Features: Fast response | Real-time display | Direct conversation[/]")
            ctx.console.print(f"[dim]Switch: Type 'mode agent' to use tool functionality[/]")
        else:
            ctx.console.print(f"[blue]Current Mode: Agent Mode (Tool Calling)[/]")
            ctx.console.print(f"[dim]Model Features: Smart reasoning | Tool calling | Session memory[/]")
            ctx.console.print(f"[dim]Switch: Type 'mode llm' to use fast conversation[/]")

        # Main loop
        while True:
            try:
                # Dynamic prompt showing current mode
                if ctx.dify_mode:
                    mode_indicator = "Dify"
                    stream_indicator = "[Cloud]"
                else:
                    mode_indicator = "LLM" if ctx.llm_mode else "Agent"
                    stream_indicator = "[S]" if (ctx.llm_mode and ctx.streaming_enabled) else ""
                
                prompt = f"\n[bold cyan]{mode_indicator}{stream_indicator}[/] > "
                query = await asyncio.to_thread(ctx.console.input, prompt)

                # Check if input is command or conversation
                if not is_command(query):
                    # Handle conversation (non-command input)
                    if not query.strip():
                        continue

                    # Handle Dify mode queries
                    if ctx.dify_mode:
                        from src.components.dify.control import handle_dify_query
                        result = await handle_dify_query(ctx, query)
                        continue

                    # Handle user queries based on working mode
                    if ctx.llm_mode:
                        # LLM mode: Direct interaction with LLM, supports streaming output and memory
                        try:
                            # Import necessary message types
                            from langchain_core.messages import HumanMessage, AIMessage

                            # Get Agent's LLM info
                            info = ctx.agent.get_info()
                            provider = info.get('provider', 'unknown')

                            if ctx.streaming_enabled:
                                # Streaming mode (with memory)
                                if hasattr(ctx.agent, 'get_llm') and callable(getattr(ctx.agent, 'get_llm')):
                                    llm = ctx.agent.get_llm()

                                    # Get history for context
                                    history = ctx.global_memory.get_session_history(ctx.session_id)
                                    context_messages = history.messages[-10:] if history.messages else []

                                    # Build prompt with history
                                    full_prompt = query
                                    if context_messages:
                                        context_text = "\n".join([f"{'User' if isinstance(msg, HumanMessage) else 'AI'}: {msg.content}" for msg in context_messages[-6:]])
                                        full_prompt = f"History:\n{context_text}\n\nCurrent Question: {query}"

                                    # Execute streaming output
                                    ctx.console.print(f"[dim]LLM streaming generation...[/]")
                                    answer = await stream_llm_response(
                                        provider=provider,
                                        prompt=full_prompt,
                                        llm=llm,
                                        display_title=f"LLM Response ({provider})",
                                        show_display=True
                                    )

                                    # Save conversation to memory
                                    ctx.global_memory.add_llm_conversation(ctx.session_id, query, answer)

                                else:
                                    ctx.console.print("[red]Unable to get LLM instance[/]")
                                    continue
                            else:
                                # Non-streaming LLM mode (with memory)
                                llm = ctx.agent.get_llm()

                                # Get history for context
                                history = ctx.global_memory.get_session_history(ctx.session_id)
                                context_messages = history.messages[-10:] if history.messages else []

                                # Build prompt with history
                                full_prompt = query
                                if context_messages:
                                    context_text = "\n".join([f"{'User' if isinstance(msg, HumanMessage) else 'AI'}: {msg.content}" for msg in context_messages[-6:]])
                                    full_prompt = f"History:\n{context_text}\n\nCurrent Question: {query}"

                                with ctx.console.status("[dim]LLM thinking...[/]"):
                                    response = await llm.ainvoke([HumanMessage(content=full_prompt)])
                                    answer = response.content if hasattr(response, 'content') else str(response)

                                ctx.console.print(f"[bold green]LLM >[/] {answer}")

                                # Save conversation to memory
                                ctx.global_memory.add_llm_conversation(ctx.session_id, query, answer)

                        except Exception as e:
                            ctx.console.print(f"[red]LLM mode processing failed: {str(e)}[/]")

                    else:
                        # Agent mode: Full Agent functionality, including tool calling and memory (no streaming output)
                        try:
                            with ctx.console.status("[dim]Agent reasoning...[/]"):
                                result = await ctx.agent.ainvoke(query, session_id=ctx.session_id)

                            if result.get("success"):
                                answer = result.get("output", "Sorry, I can't answer that question.")
                                ctx.console.print(f"[bold blue]Agent >[/] {answer}")

                                # Show tool call information
                                if result.get("tool_calls", 0) > 0:
                                    tool_names = result.get("tool_names", [])
                                    if tool_names:
                                        tools_str = ", ".join(tool_names)
                                        ctx.console.print(f"[dim]Used {result['tool_calls']} tool calls: {tools_str}[/]")
                                    else:
                                        ctx.console.print(f"[dim]Used {result['tool_calls']} tool calls[/]")

                                # Agent mode conversations are automatically saved to memory through RunnableWithMessageHistory
                                # No manual saving needed as Agent already integrates global memory manager

                            else:
                                ctx.console.print(f"[bold red]Agent Error: {result.get('error', 'Unknown error')}[/]")

                        except Exception as e:
                            ctx.console.print(f"[red]Agent mode processing failed: {str(e)}[/]")
                else:
                    # Handle command
                    command, args = parse_command(query)
                    command_name = extract_command_name(command)

                    if command_name.lower() in {"exit", "quit"}:
                        # Clean up resources gracefully
                        ctx.console.print("[dim]Cleaning up resources...[/]")

                        # Clean up Dify controller resources
                        if ctx.dify_control:
                            try:
                                await ctx.dify_control.cleanup()
                                ctx.dify_control = None
                            except Exception as e:
                                logger.warning(f"Error during Dify cleanup: {e}")

                        # Cancel any pending background tasks
                        try:
                            pending = asyncio.all_tasks()
                            current_task = asyncio.current_task()
                            # Cancel all tasks except the current one
                            for task in pending:
                                if task is not current_task and not task.done():
                                    task.cancel()
                            # Wait briefly for tasks to cancel
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            logger.warning(f"Error during task cleanup: {e}")

                        ctx.console.print("Goodbye!")
                        break

                    if command_name.lower() == "help":
                        gui.print_help(ctx.console, dify_mode=ctx.dify_mode)
                        continue

                    if command_name.lower() == "info":
                        if ctx.dify_mode:
                            # Dify mode info command
                            if ctx.dify_control:
                                dify_info = await ctx.dify_control.get_detailed_info()
                                gui.render_dify_info(ctx.console, dify_info, ctx.session_id)
                            else:
                                ctx.console.print("[red]Dify controller not initialized[/]")
                        else:
                            # LLM mode info command
                            result = control.get_info(ctx)
                            if result["type"] == "info":
                                gui.render_info(ctx.console, result["payload"]["agent"], result["payload"]["mode"])
                        continue

                    if command_name.lower() in {"llms", "llm"}:
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]LLM catalog is not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify mode uses cloud AI service. Use '/switch <provider>' to exit and view local LLM options.[/]")
                            continue
                        catalog = await registry.get_catalog()
                        gui.render_llms(ctx.console, catalog)
                        continue

                    # MCP commands
                    if command_name.lower() == "mcp":
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]MCP commands are not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify mode uses cloud AI service. Use '/switch <provider>' to exit and access MCP tools.[/]")
                            continue
                        sub = args.split()[0].lower() if args else ""

                        if sub in {"status", "tools", "reload"}:
                            if not MCP_AVAILABLE or GlobalMCPManager is None:
                                ctx.console.print("[yellow]MCP manager is not available (missing dependencies or not integrated)[/]")
                                continue

                            if sub == "status":
                                verbose = any(a in ["-v", "--verbose"] for a in args.split()[1:] if args)
                                result = await mcp_control.mcp_status(verbose=verbose)
                                if result["type"] == "status":
                                    gui.render_mcp_status(ctx.console, result["payload"], verbose=verbose)
                                elif result["type"] == "error":
                                    ctx.console.print(f"[red]Error: {result['message']}[/]")
                                continue

                            if sub == "tools":
                                json_flag = any(a == "--json" for a in args.split()[1:] if args)
                                result = await mcp_control.mcp_tools(json_flag=json_flag)
                                if result["type"] == "list":
                                    gui.render_mcp_tools(ctx.console, result["payload"]["tools"], json_flag=json_flag)
                                elif result["type"] == "error":
                                    ctx.console.print(f"[red]Error: {result['message']}[/]")
                                continue

                            if sub == "reload":
                                result = await mcp_control.mcp_reload()
                                if result["type"] == "success":
                                    import json
                                    ctx.console.print("[green]MCP configuration reloaded successfully[/]")
                                    ctx.console.print(json.dumps(result["payload"], ensure_ascii=False, indent=2))
                                elif result["type"] == "error":
                                    ctx.console.print(f"[red]Error: {result['message']}[/]")
                                continue

                        ctx.console.print("[yellow]Usage: /mcp status [-v] | /mcp tools [--json] | /mcp reload[/]")
                        continue

                    # Connector commands
                    if command_name.lower() == "connector":
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]Connector commands are not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify mode uses cloud AI service. Use '/switch <provider>' to exit and access connector tools.[/]")
                            continue
                        sub = args.split()[0].lower() if args else ""

                        if sub in {"status", "tools", "reload"}:
                            if sub == "status":
                                verbose = any(a in ["-v", "--verbose"] for a in args.split()[1:] if args)
                                result = await connector_status(verbose=verbose)
                                if result["type"] == "status":
                                    from .gui import render_connector_status
                                    render_connector_status(ctx.console, result["payload"], verbose=verbose)
                                elif result["type"] == "error":
                                    ctx.console.print(f"[red]Error: {result['message']}[/]")
                                continue

                            if sub == "tools":
                                json_flag = any(a == "--json" for a in args.split()[1:] if args)
                                result = await connector_tools(json_flag=json_flag)
                                if result["type"] == "list":
                                    from .gui import render_connector_tools
                                    render_connector_tools(ctx.console, result["payload"]["tools"], json_flag=json_flag)
                                elif result["type"] == "error":
                                    ctx.console.print(f"[red]Error: {result['message']}[/]")
                                continue

                            if sub == "reload":
                                result = await connector_reload()
                                if result["type"] == "success":
                                    ctx.console.print("[green]Connector reloaded successfully[/]")
                                    ctx.console.print(result["message"])
                                elif result["type"] == "error":
                                    ctx.console.print(f"[red]Error: {result['message']}[/]")
                                continue

                        ctx.console.print("[yellow]Usage: /connector status [-v] | /connector tools [--json] | /connector reload[/]")
                        continue

                    # Switch command
                    if command_name.lower() == "switch":
                        if not args:
                            ctx.console.print("[yellow]Usage: /switch <provider> [model] | /switch dify[/]")
                            ctx.console.print("[dim]Example: /switch openai gpt-4o-mini[/]")
                            ctx.console.print("[dim]Example: /switch dify[/]")
                            continue

                        # Parse provider and model from args
                        args_parts = args.split()
                        provider = args_parts[0].lower()
                        model = args_parts[1] if len(args_parts) > 1 else None

                        # Handle Dify switch
                        if provider == "dify":
                            # Check if already in Dify mode
                            if ctx.dify_mode and ctx.dify_control and ctx.dify_control.is_initialized:
                                ctx.console.print("[yellow]Already in Dify mode[/]")
                                ctx.console.print("[dim]Current status: Connected | Session ID: " +
                                    (ctx.dify_control.conversation_id or "Not created") + "[/]")
                                ctx.console.print("[dim]To reinitialize, switch to another mode first[/]")
                                continue

                            from src.components.dify.control import init_dify_client
                            with ctx.console.status("[yellow]Initializing Dify client...[/]"):
                                result = await init_dify_client(ctx)

                            if result["type"] == "success":
                                ctx.dify_mode = True
                                ctx.console.print("[green]Switched to Dify mode[/]")
                                ctx.console.print("[dim]Features: File upload | Streaming conversation | Cloud AI[/]")
                                ctx.console.print("[dim]Commands:[/]")
                                ctx.console.print("[dim]  /upload           - Upload files (support multi-select)[/]")
                                ctx.console.print("[dim]  /files            - List uploaded files[/]")
                                ctx.console.print("[dim]  /files remove <#> - Remove file by index[/]")
                                ctx.console.print("[dim]  /files clear      - Clear all files[/]")
                                ctx.console.print("[dim]  /reset            - Reset conversation[/]")
                            else:
                                ctx.console.print(f"[red]Switch failed: {result['message']}[/]")
                            continue

                        # Handle regular LLM switch
                        # Switch LLM (exit Dify mode if active)
                        if ctx.dify_mode:
                            ctx.dify_mode = False
                            if ctx.dify_control:
                                await ctx.dify_control.cleanup()
                                ctx.dify_control = None
                            ctx.console.print("[dim]Exited Dify mode[/]")

                        with ctx.console.status(f"[yellow]Switching to {provider} {model or '(default model)'}...[/]"):
                            result = await control.switch_llm(ctx, provider, model)
                        if result["type"] == "error":
                            ctx.console.print(f"[red]{result['message']}[/]")
                            if "payload" in result and "available_providers" in result["payload"]:
                                ctx.console.print(f"[dim]Available providers: {', '.join(result['payload']['available_providers'])}[/]")
                        continue

                    # Dify specific commands
                    if ctx.dify_mode:
                        if command_name.lower() == "upload":
                            from src.components.dify.control import handle_dify_upload
                            result = await handle_dify_upload(ctx, args)
                            continue

                        if command_name.lower() == "reset":
                            if ctx.dify_control:
                                await ctx.dify_control.reset_conversation()
                            continue

                        # Enhanced /files command with subcommands
                        if command_name.lower() in {"files", "listfiles"}:
                            if not ctx.dify_control:
                                ctx.console.print("[yellow]Dify client not initialized[/]")
                                continue

                            # Parse subcommand
                            subcommand_parts = args.split() if args else []
                            subcommand = subcommand_parts[0].lower() if subcommand_parts else "list"

                            if subcommand == "list" or not subcommand_parts:
                                # List all files
                                await ctx.dify_control.list_files()

                            elif subcommand == "clear":
                                # Clear all files
                                await ctx.dify_control.clear_files()

                            elif subcommand == "remove":
                                # Remove specific files by index
                                if len(subcommand_parts) < 2:
                                    ctx.console.print("[yellow]Usage: /files remove <index> [index2] [index3] ...[/]")
                                    ctx.console.print("[dim]Example: /files remove 2[/]")
                                    ctx.console.print("[dim]Example: /files remove 1 3 5[/]")
                                    continue

                                # Parse indices
                                indices = []
                                for idx_str in subcommand_parts[1:]:
                                    try:
                                        idx = int(idx_str)
                                        indices.append(idx)
                                    except ValueError:
                                        ctx.console.print(f"[yellow]Invalid index: {idx_str}[/]")

                                if not indices:
                                    ctx.console.print("[yellow]No valid indices provided[/]")
                                    continue

                                # Remove files
                                if len(indices) == 1:
                                    await ctx.dify_control.remove_file(indices[0])
                                else:
                                    await ctx.dify_control.remove_files_by_indices(indices)

                            else:
                                ctx.console.print(f"[yellow]Unknown subcommand: {subcommand}[/]")
                                ctx.console.print("[yellow]Usage: /files [list|clear|remove <index>...][/]")
                                ctx.console.print("[dim]  /files          - List all files[/]")
                                ctx.console.print("[dim]  /files list     - List all files[/]")
                                ctx.console.print("[dim]  /files clear    - Clear all files[/]")
                                ctx.console.print("[dim]  /files remove 2 - Remove file #2[/]")

                            continue

                        # Deprecated: kept for backward compatibility
                        if command_name.lower() == "clearfiles":
                            if ctx.dify_control:
                                await ctx.dify_control.clear_files()
                            continue

                        if command_name.lower() == "reconnect":
                            from src.components.dify.control import init_dify_client
                            with ctx.console.status("[yellow]Reconnecting Dify client...[/]"):
                                result = await init_dify_client(ctx, force_reinit=True)

                            if result["type"] == "success":
                                ctx.console.print("[green]Dify client reconnected successfully[/]")
                            else:
                                ctx.console.print(f"[red]Reconnection failed: {result['message']}[/]")
                            continue

                    # Session commands
                    if command_name.lower() == "clear":
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]/clear is not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify uses cloud-based conversation management. Use '/reset' to reset Dify conversation[/]")
                            continue

                        result = session_control.clear_session(ctx)
                        if result["type"] == "success":
                            ctx.console.print("[green]Current session memory cleared[/]")
                        else:
                            ctx.console.print("[yellow]Failed to clear memory[/]")
                        continue

                    if command_name.lower() == "new":
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]/new is not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify uses cloud-based conversation management. Use '/reset' to start a new conversation[/]")
                            continue

                        result = session_control.new_session(ctx)
                        if result["type"] == "success":
                            ctx.console.print(f"[green]{result['message']}[/]")
                            ctx.console.print(f"[dim]Previous session {result['payload']['old_session_id']} saved[/]")
                        continue

                    if command_name.lower() == "delete_session":
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]/delete_session is not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify uses cloud-based conversation management. Session management is handled by Dify platform[/]")
                            continue

                        if args:
                            result = session_control.delete_session(ctx, args)
                            if result["type"] == "success":
                                ctx.console.print(f"[green]{result['message']}[/]")
                            else:
                                ctx.console.print(f"[red]{result['message']}[/]")
                        else:
                            ctx.console.print("[yellow]Please provide a valid session ID, format: /delete_session <session_id>[/]")
                        continue

                    if command_name.lower() == "cleanup":
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]/cleanup is not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify uses cloud-based conversation management. No local session files to clean[/]")
                            continue

                        result = session_control.cleanup_sessions(ctx)
                        if result["type"] == "success":
                            ctx.console.print(f"[green]{result['message']}[/]")
                            ctx.console.print(f"[dim]  Cleaned orphaned index entries: {result['payload']['orphaned_index_entries']}[/]")
                            ctx.console.print(f"[dim]  Cleaned orphaned files: {result['payload']['orphaned_files']}[/]")
                        continue

                    if command_name.lower() in {"sessions", "ls"}:
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]/sessions is not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify uses cloud-based conversation management. Sessions are managed on Dify platform[/]")
                            continue

                        result = session_control.list_sessions(ctx)
                        if result["type"] == "list":
                            gui.render_sessions(ctx.console, result["payload"]["sessions"], result["payload"]["current_session_id"])
                        continue

                    if command_name.lower() == "restore":
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]/restore is not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify uses cloud-based conversation management. Switch to local mode to restore sessions[/]")
                            continue

                        if args:
                            result = session_control.restore_session(ctx, args)
                            if result["type"] == "success":
                                ctx.console.print(f"[green]{result['message']}[/]")
                                if "session_info" in result["payload"]:
                                    ctx.console.print(f"[dim]Message count: {result['payload']['session_info']['message_count']} | Created: {result['payload']['session_info'].get('created_at', '')[:19]}[/]")
                            else:
                                ctx.console.print(f"[red]{result['message']}[/]")
                        else:
                            ctx.console.print("[yellow]Please provide a valid session ID, format: /restore <session_id>[/]")
                        continue

                    # Reload configuration command
                    if command_name.lower() == "reload":
                        result = control.reload_config(ctx)
                        if result["type"] == "success":
                            ctx.console.print(f"[green]{result['message']}[/]")
                            if "note" in result["payload"]:
                                ctx.console.print(f"[dim]{result['payload']['note']}[/]")
                        else:
                            ctx.console.print(f"[red]{result['message']}[/]")
                        continue

                    # Mode commands
                    if command_name.lower() == "mode":
                        # Disable mode switching in Dify mode
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]Mode switching is not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify mode is a standalone cloud AI service. Use '/switch <provider>' to exit and switch to local LLM modes.[/]")
                            continue

                        if not args:
                            current_mode = "LLM Mode" if ctx.llm_mode else "Agent Mode"
                            ctx.console.print(f"[yellow]Usage: /mode llm/agent[/]")
                            ctx.console.print(f"[dim]Current mode: {current_mode}[/]")
                            continue

                        mode = args.lower()
                        result = control.set_mode(ctx, mode)
                        if result["type"] == "success":
                            if ctx.llm_mode:
                                ctx.console.print("[green]Switched to LLM mode (streaming output)[/]")
                                ctx.console.print("[dim]Features: Fast response | Real-time display | Direct conversation[/]")
                                ctx.console.print("[dim]Use case: Daily chat, text generation, quick Q&A[/]")
                            else:
                                ctx.console.print("[blue]Switched to Agent mode (tool calling)[/]")
                                ctx.console.print("[dim]Features: Smart reasoning | Tool calling | Session memory[/]")
                                ctx.console.print("[dim]Use case: Search queries, calculation analysis, complex tasks[/]")
                        else:
                            ctx.console.print(f"[yellow]{result['message']}[/]")
                        continue

                    # Stream commands
                    if command_name.lower() == "stream":
                        # Disable stream control in Dify mode
                        if ctx.dify_mode:
                            ctx.console.print("[yellow]Stream control is not available in Dify mode[/]")
                            ctx.console.print("[dim]Dify mode uses built-in streaming. Use '/switch <provider>' to exit and switch to local LLM modes.[/]")
                            continue

                        # Parse stream command (only effective in LLM mode)
                        if not ctx.llm_mode:
                            ctx.console.print("[yellow]Streaming output is only available in LLM mode, please switch to LLM mode first[/]")
                            ctx.console.print("[dim]Use '/mode llm' to switch to LLM mode[/]")
                            continue

                        if not args:
                            ctx.console.print("[yellow]Usage: /stream on/off[/]")
                            ctx.console.print(f"[dim]LLM streaming output status: {'Enabled' if ctx.streaming_enabled else 'Disabled'}[/]")
                            continue

                        action = args.lower()
                        result = control.set_stream(ctx, action)
                        if result["type"] == "success":
                            if ctx.streaming_enabled:
                                ctx.console.print("[green]LLM streaming output enabled[/]")
                            else:
                                ctx.console.print("[yellow]LLM streaming output disabled[/]")
                        else:
                            ctx.console.print(f"[yellow]{result['message']}[/]")
                        continue

                    # Unknown command
                    ctx.console.print(f"[yellow]Unknown command: {command}[/]")
                    ctx.console.print("[dim]Type '/help' for available commands[/]")
                    continue


            except KeyboardInterrupt:
                ctx.console.print("\n[yellow]Interrupted. Cleaning up...[/]")
                # Clean up Dify resources on interrupt
                if ctx.dify_control:
                    try:
                        await ctx.dify_control.cleanup()
                    except Exception as e:
                        logger.warning(f"Error during interrupt cleanup: {e}")
                ctx.console.print("Goodbye!")
                break
            except Exception as e:
                ctx.console.print(f"[bold red]Error: {e}")

    except Exception as e:
        ctx.console.print(f"[bold red]Agent initialization failed: {e}[/]")
        ctx.console.print("Please check your API keys and network connection")
    finally:
        # Final cleanup - ensure Dify resources are released
        if hasattr(ctx, 'dify_control') and ctx.dify_control:
            try:
                await ctx.dify_control.cleanup()
            except Exception as e:
                logger.warning(f"Error during final cleanup: {e}")