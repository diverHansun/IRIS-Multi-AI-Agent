"""
CLI module for the Multi-AI-Agent project.
This module contains the main CLI loop and command routing.
"""

import asyncio
from rich.console import Console

from src.agents.agent_factory import create_default_agent, get_available_configurations
from src.llm.streaming_llm import stream_llm_response
from src.memory import GlobalMemoryManager, SessionManager

# Try to import MCP manager
try:
    from src.MCP import GlobalMCPManager
    MCP_AVAILABLE = True
except Exception:
    GlobalMCPManager = None
    MCP_AVAILABLE = False

# Import components
from . import control, session_control, mcp_control, registry, gui


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


async def run():
    """Main CLI loop"""
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
        ctx.console.print(f"[green]Agent initialized successfully![/]")
        ctx.console.print(f"[dim]Provider: {info['provider']}, Model: {info['model']}, Tool Count: {info['tool_count']}[/]")
        
        # Show current mode and prompt
        if ctx.llm_mode:
            ctx.console.print(f"[green]Current Mode: LLM Mode (Streaming Output)[/]")
            ctx.console.print(f"[dim]Features: Fast response | Real-time display | Direct conversation[/]")
            ctx.console.print(f"[dim]Switch: Type 'mode agent' to use tool functionality[/]")
        else:
            ctx.console.print(f"[blue]Current Mode: Agent Mode (Tool Calling)[/]")
            ctx.console.print(f"[dim]Features: Smart reasoning | Tool calling | Session memory[/]")
            ctx.console.print(f"[dim]Switch: Type 'mode llm' to use fast conversation[/]")

        # Main loop
        while True:
            try:
                # Dynamic prompt showing current mode
                mode_indicator = "LLM" if ctx.llm_mode else "Agent"
                stream_indicator = "[S]" if (ctx.llm_mode and ctx.streaming_enabled) else ""
                
                prompt = f"\n[bold cyan]{mode_indicator}{stream_indicator}[/] > "
                query = await asyncio.to_thread(ctx.console.input, prompt)

                if query.strip().lower() in {"exit", "quit"}:
                    ctx.console.print("[yellow]Goodbye![/]")
                    break

                if query.strip().lower() in {"help"}:
                    gui.print_help(ctx.console)
                    continue

                if query.strip().lower() in {"info"}:
                    result = control.get_info(ctx)
                    if result["type"] == "info":
                        gui.render_info(ctx.console, result["payload"]["agent"], result["payload"]["mode"])
                    continue

                if query.strip().lower() in {"llms", "llm"}:
                    catalog = await registry.get_catalog()
                    gui.render_llms(ctx.console, catalog)
                    continue

                # MCP commands
                if query.strip().lower().startswith("mcp "):
                    parts = query.strip().split()
                    sub = parts[1].lower() if len(parts) > 1 else ""
                    
                    if sub in {"status", "tools", "reload"}:
                        if not MCP_AVAILABLE or GlobalMCPManager is None:
                            ctx.console.print("[yellow]MCP manager is not available (missing dependencies or not integrated)[/]")
                            continue
                        
                        if sub == "status":
                            verbose = any(a in ["-v", "--verbose"] for a in parts[2:])
                            result = await mcp_control.mcp_status(verbose=verbose)
                            if result["type"] == "status":
                                gui.render_mcp_status(ctx.console, result["payload"], verbose=verbose)
                            elif result["type"] == "error":
                                ctx.console.print(f"[red]Error: {result['message']}[/]")
                            continue
                        
                        if sub == "tools":
                            json_flag = any(a == "--json" for a in parts[2:])
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
                    
                    ctx.console.print("[yellow]Usage: mcp status [-v] | mcp tools [--json] | mcp reload[/]")
                    continue

                # Switch command
                if query.strip().lower().startswith("switch "):
                    # Parse switch command
                    parts = query.strip().split()
                    if len(parts) < 2:
                        ctx.console.print("[yellow]⚠️ Usage: switch <provider> [model][/]")
                        ctx.console.print("[dim]Example: switch openai gpt-4o-mini[/]")
                        continue

                    provider = parts[1]
                    model = parts[2] if len(parts) > 2 else None

                    # Switch LLM
                    with ctx.console.status(f"[yellow]Switching to {provider} {model or '(default model)'}...[/]"):
                        result = await control.switch_llm(ctx, provider, model)
                    if result["type"] == "error":
                        ctx.console.print(f"[red]❌ {result['message']}[/]")
                        if "payload" in result and "available_providers" in result["payload"]:
                            ctx.console.print(f"[dim]Available providers: {', '.join(result['payload']['available_providers'])}[/]")
                    continue

                # Session commands
                if query.strip().lower() in {"clear"}:
                    result = session_control.clear_session(ctx)
                    if result["type"] == "success":
                        ctx.console.print("[green]✅ Current session memory cleared[/]")
                    else:
                        ctx.console.print("[yellow]⚠️ Failed to clear memory[/]")
                    continue

                if query.strip().lower() in {"new"}:
                    result = session_control.new_session(ctx)
                    if result["type"] == "success":
                        ctx.console.print(f"[green]✅ {result['message']}[/]")
                        ctx.console.print(f"[dim]Previous session {result['payload']['old_session_id']} saved[/]")
                    continue

                if query.strip().lower().startswith("delete_session "):
                    target_session_id = query.strip()[15:].strip()
                    if target_session_id:
                        result = session_control.delete_session(ctx, target_session_id)
                        if result["type"] == "success":
                            ctx.console.print(f"[green]✅ {result['message']}[/]")
                        else:
                            ctx.console.print(f"[red]❌ {result['message']}[/]")
                    else:
                        ctx.console.print("[yellow]⚠️ Please provide a valid session ID, format: delete_session <session_id>[/]")
                    continue

                if query.strip().lower() in {"cleanup"}:
                    result = session_control.cleanup_sessions(ctx)
                    if result["type"] == "success":
                        ctx.console.print(f"[green]✅ {result['message']}[/]")
                        ctx.console.print(f"[dim]  Cleaned orphaned index entries: {result['payload']['orphaned_index_entries']}[/]")
                        ctx.console.print(f"[dim]  Cleaned orphaned files: {result['payload']['orphaned_files']}[/]")
                    continue

                if query.strip().lower() in {"sessions", "ls"}:
                    result = session_control.list_sessions(ctx)
                    if result["type"] == "list":
                        gui.render_sessions(ctx.console, result["payload"]["sessions"], result["payload"]["current_session_id"])
                    continue

                if query.strip().lower().startswith("restore "):
                    target_session_id = query.strip()[8:].strip()
                    if target_session_id:
                        result = session_control.restore_session(ctx, target_session_id)
                        if result["type"] == "success":
                            ctx.console.print(f"[green]✅ {result['message']}[/]")
                            if "session_info" in result["payload"]:
                                ctx.console.print(f"[dim]Message count: {result['payload']['session_info']['message_count']} | Created: {result['payload']['session_info'].get('created_at', '')[:19]}[/]")
                        else:
                            ctx.console.print(f"[red]❌ {result['message']}[/]")
                    else:
                        ctx.console.print("[yellow]⚠️ Please provide a valid session ID, format: restore <session_id>[/]")
                    continue

                # Mode commands
                if query.strip().lower().startswith("mode "):
                    # Parse mode command
                    parts = query.strip().split()
                    if len(parts) < 2:
                        current_mode = "LLM Mode" if ctx.llm_mode else "Agent Mode"
                        ctx.console.print(f"[yellow]⚠️ Usage: mode llm/agent[/]")
                        ctx.console.print(f"[dim]Current mode: {current_mode}[/]")
                        continue

                    mode = parts[1].lower()
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
                        ctx.console.print(f"[yellow]⚠️ {result['message']}[/]")
                    continue

                # Stream commands
                if query.strip().lower().startswith("stream "):
                    # Parse stream command (only effective in LLM mode)
                    if not ctx.llm_mode:
                        ctx.console.print("[yellow]⚠️ Streaming output is only available in LLM mode, please switch to LLM mode first[/]")
                        ctx.console.print("[dim]Use 'mode llm' to switch to LLM mode[/]")
                        continue
                        
                    parts = query.strip().split()
                    if len(parts) < 2:
                        ctx.console.print("[yellow]⚠️ Usage: stream on/off[/]")
                        ctx.console.print(f"[dim]LLM streaming output status: {'Enabled' if ctx.streaming_enabled else 'Disabled'}[/]")
                        continue

                    action = parts[1].lower()
                    result = control.set_stream(ctx, action)
                    if result["type"] == "success":
                        if ctx.streaming_enabled:
                            ctx.console.print("[green]✅ LLM streaming output enabled[/]")
                        else:
                            ctx.console.print("[yellow]⚠️ LLM streaming output disabled[/]")
                    else:
                        ctx.console.print(f"[yellow]⚠️ {result['message']}[/]")
                    continue

                if not query.strip():
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
                                ctx.console.print("[red]❌ Unable to get LLM instance[/]")
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
                        ctx.console.print(f"[red]❌ LLM mode processing failed: {str(e)}[/]")
                        
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
                                ctx.console.print(f"[dim]Used {result['tool_calls']} tool calls[/]")
                            
                            # Agent mode conversations are automatically saved to memory through RunnableWithMessageHistory
                            # No manual saving needed as Agent already integrates global memory manager
                            
                        else:
                            ctx.console.print(f"[bold red]Agent Error: {result.get('error', 'Unknown error')}[/]")
                            
                    except Exception as e:
                        ctx.console.print(f"[red]❌ Agent mode processing failed: {str(e)}[/]")

            except KeyboardInterrupt:
                ctx.console.print("\n[yellow]Goodbye![/]")
                break
            except Exception as e:
                ctx.console.print(f"[bold red]Error: {e}")

    except Exception as e:
        ctx.console.print(f"[bold red]Agent initialization failed: {e}[/]")
        ctx.console.print("Please check your API keys and network connection")