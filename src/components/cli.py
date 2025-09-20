"""
CLI module for the Multi-AI-Agent project.
This module contains the main CLI loop and command routing.
"""

import asyncio
from rich.console import Console

# Import the IRIS logo display function
from src.ui.logo.logo import display_logo,display_logo_intro

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
        # Dify integration
        self.dify_mode = False  # Dify mode flag
        self.dify_control = None  # Dify control instance


def parse_command(query: str) -> tuple[str, str]:
    """
    解析命令，智能处理空格和前缀
    
    Args:
        query: 用户输入的命令
        
    Returns:
        (命令部分, 参数部分) 的元组
    """
    # 去除前后空格
    query = query.strip()
    
    if not query:
        return "", ""
    
    # 移除 / 前缀
    if query.startswith('/'):
        query = query[1:]
    
    # 分割命令和参数
    parts = query.split(' ', 1)
    command = parts[0].strip() if parts else ""
    args = parts[1].strip() if len(parts) > 1 else ""
    
    return command, args


def normalize_command(query: str) -> str:
    """
    标准化命令，移除/前缀以便统一处理，但保留参数间的空格
    
    Args:
        query: 用户输入的命令
        
    Returns:
        标准化后的命令（移除开头的/，保留参数间空格）
    """
    command, args = parse_command(query)
    
    if args:
        return f"{command} {args}"
    else:
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
        ctx.console.print(f"[green]Agent initialized successfully![/]")
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
                    stream_indicator = "☁️"
                else:
                    mode_indicator = "LLM" if ctx.llm_mode else "Agent"
                    stream_indicator = "[S]" if (ctx.llm_mode and ctx.streaming_enabled) else ""
                
                prompt = f"\n[bold cyan]{mode_indicator}{stream_indicator}[/] > "
                query = await asyncio.to_thread(ctx.console.input, prompt)

                # 标准化命令，移除/前缀
                normalized_query = normalize_command(query)

                if normalized_query.lower() in {"exit", "quit"}:
                    # 清理 Dify 控制器资源
                    if ctx.dify_control:
                        await ctx.dify_control.cleanup()
                        ctx.dify_control = None
                    ctx.console.print("[yellow]Goodbye![/]")
                    break

                if normalized_query.lower() in {"help"}:
                    gui.print_help(ctx.console, dify_mode=ctx.dify_mode)
                    continue

                if normalized_query.lower() in {"info"}:
                    if ctx.dify_mode:
                        # Dify 模式下的 info 命令
                        if ctx.dify_control:
                            dify_info = await ctx.dify_control.get_detailed_info()
                            gui.render_dify_info(ctx.console, dify_info, ctx.session_id)
                        else:
                            ctx.console.print("[red]❌ Dify 控制器未初始化[/]")
                    else:
                        # LLM 模式下的 info 命令
                        result = control.get_info(ctx)
                        if result["type"] == "info":
                            gui.render_info(ctx.console, result["payload"]["agent"], result["payload"]["mode"])
                    continue

                if normalized_query.lower() in {"llms", "llm"}:
                    if ctx.dify_mode:
                        ctx.console.print("[yellow]⚠️ LLM catalog is not available in Dify mode[/]")
                        ctx.console.print("[dim]Dify mode uses cloud AI service. Use '/switch dify' to exit and view local LLM options.[/]")
                        continue
                    catalog = await registry.get_catalog()
                    gui.render_llms(ctx.console, catalog)
                    continue

                # MCP commands
                if normalized_query.lower().startswith("mcp "):
                    if ctx.dify_mode:
                        ctx.console.print("[yellow]⚠️ MCP commands are not available in Dify mode[/]")
                        ctx.console.print("[dim]Dify mode uses cloud AI service. Use '/switch dify' to exit and access MCP tools.[/]")
                        continue
                    command, args = parse_command(query)
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

                # Switch command
                if normalized_query.lower().startswith("switch "):
                    # Parse switch command using new parser
                    command, args = parse_command(query)
                    if not args:
                        ctx.console.print("[yellow]⚠️ Usage: /switch <provider> [model] | /switch dify[/]")
                        ctx.console.print("[dim]Example: /switch openai gpt-4o-mini[/]")
                        ctx.console.print("[dim]Example: /switch dify[/]")
                        continue

                    # Parse provider and model from args
                    args_parts = args.split()
                    provider = args_parts[0].lower()
                    model = args_parts[1] if len(args_parts) > 1 else None

                    # Handle Dify switch
                    if provider == "dify":
                        # 检查是否已经在 Dify 模式
                        if ctx.dify_mode and ctx.dify_control and ctx.dify_control.is_initialized:
                            ctx.console.print("[yellow]⚠️ 已经在 Dify 模式中[/]")
                            ctx.console.print("[dim]当前状态: 已连接 | 会话ID: " + 
                                (ctx.dify_control.conversation_id or "未创建") + "[/]")
                            ctx.console.print("[dim]如需重新初始化，请先切换到其他模式再切换回来[/]")
                            continue
                        
                        from src.components.dify.control import init_dify_client
                        with ctx.console.status("[yellow]初始化 Dify 客户端...[/]"):
                            result = await init_dify_client(ctx)
                        
                        if result["type"] == "success":
                            ctx.dify_mode = True
                            ctx.console.print("[green]✅ 已切换到 Dify 模式[/]")
                            ctx.console.print("[dim]Features: 文件上传 | 流式对话 | 云端智能[/]")
                            ctx.console.print("[dim]Commands: /upload (上传文件) | /reset (重置会话)[/]")
                        else:
                            ctx.console.print(f"[red]❌ 切换失败: {result['message']}[/]")
                        continue

                    # Handle regular LLM switch
                    # model already parsed above

                    # Switch LLM (exit Dify mode if active)
                    if ctx.dify_mode:
                        ctx.dify_mode = False
                        if ctx.dify_control:
                            await ctx.dify_control.cleanup()
                            ctx.dify_control = None
                        ctx.console.print("[dim]已退出 Dify 模式[/]")

                    with ctx.console.status(f"[yellow]Switching to {provider} {model or '(default model)'}...[/]"):
                        result = await control.switch_llm(ctx, provider, model)
                    if result["type"] == "error":
                        ctx.console.print(f"[red]❌ {result['message']}[/]")
                        if "payload" in result and "available_providers" in result["payload"]:
                            ctx.console.print(f"[dim]Available providers: {', '.join(result['payload']['available_providers'])}[/]")
                    continue

                # Dify specific commands
                if ctx.dify_mode:
                    if normalized_query.lower().startswith("upload"):
                        from src.components.dify.control import handle_dify_upload
                        result = await handle_dify_upload(ctx, normalized_query)
                        continue
                    
                    if normalized_query.lower() in {"reset"}:
                        if ctx.dify_control:
                            await ctx.dify_control.reset_conversation()
                        continue
                    
                    if normalized_query.lower() in {"files", "listfiles", "list_files"}:
                        if ctx.dify_control:
                            await ctx.dify_control.list_files()
                        continue
                    
                    if normalized_query.lower() in {"clearfiles", "clear_files"}:
                        if ctx.dify_control:
                            await ctx.dify_control.clear_files()
                        continue
                    
                    if normalized_query.lower() in {"reconnect", "reconnect dify"}:
                        from src.components.dify.control import init_dify_client
                        with ctx.console.status("[yellow]重新连接 Dify 客户端...[/]"):
                            result = await init_dify_client(ctx, force_reinit=True)
                        
                        if result["type"] == "success":
                            ctx.console.print("[green]✅ Dify 客户端重新连接成功[/]")
                        else:
                            ctx.console.print(f"[red]❌ 重新连接失败: {result['message']}[/]")
                        continue

                # Session commands
                if normalized_query.lower() in {"clear"}:
                    result = session_control.clear_session(ctx)
                    if result["type"] == "success":
                        ctx.console.print("[green]✅ Current session memory cleared[/]")
                    else:
                        ctx.console.print("[yellow]⚠️ Failed to clear memory[/]")
                    continue

                if normalized_query.lower() in {"new"}:
                    result = session_control.new_session(ctx)
                    if result["type"] == "success":
                        ctx.console.print(f"[green]✅ {result['message']}[/]")
                        ctx.console.print(f"[dim]Previous session {result['payload']['old_session_id']} saved[/]")
                    continue

                if normalized_query.lower().startswith("delete_session "):
                    command, args = parse_command(query)
                    if args:
                        result = session_control.delete_session(ctx, args)
                        if result["type"] == "success":
                            ctx.console.print(f"[green]✅ {result['message']}[/]")
                        else:
                            ctx.console.print(f"[red]❌ {result['message']}[/]")
                    else:
                        ctx.console.print("[yellow]⚠️ Please provide a valid session ID, format: /delete_session <session_id>[/]")
                    continue

                if normalized_query.lower() in {"cleanup"}:
                    result = session_control.cleanup_sessions(ctx)
                    if result["type"] == "success":
                        ctx.console.print(f"[green]✅ {result['message']}[/]")
                        ctx.console.print(f"[dim]  Cleaned orphaned index entries: {result['payload']['orphaned_index_entries']}[/]")
                        ctx.console.print(f"[dim]  Cleaned orphaned files: {result['payload']['orphaned_files']}[/]")
                    continue

                if normalized_query.lower() in {"sessions", "ls"}:
                    result = session_control.list_sessions(ctx)
                    if result["type"] == "list":
                        gui.render_sessions(ctx.console, result["payload"]["sessions"], result["payload"]["current_session_id"])
                    continue

                if normalized_query.lower().startswith("restore "):
                    command, args = parse_command(query)
                    if args:
                        result = session_control.restore_session(ctx, args)
                        if result["type"] == "success":
                            ctx.console.print(f"[green]✅ {result['message']}[/]")
                            if "session_info" in result["payload"]:
                                ctx.console.print(f"[dim]Message count: {result['payload']['session_info']['message_count']} | Created: {result['payload']['session_info'].get('created_at', '')[:19]}[/]")
                        else:
                            ctx.console.print(f"[red]❌ {result['message']}[/]")
                    else:
                        ctx.console.print("[yellow]⚠️ Please provide a valid session ID, format: /restore <session_id>[/]")
                    continue

                # Reload configuration command
                if normalized_query.lower() in {"reload", "reload llm"}:
                    result = control.reload_config(ctx)
                    if result["type"] == "success":
                        ctx.console.print(f"[green]✅ {result['message']}[/]")
                        if "note" in result["payload"]:
                            ctx.console.print(f"[dim]{result['payload']['note']}[/]")
                    else:
                        ctx.console.print(f"[red]❌ {result['message']}[/]")
                    continue

                # Mode commands
                if normalized_query.lower().startswith("mode "):
                    # 在 Dify 模式下禁用模式切换命令
                    if ctx.dify_mode:
                        ctx.console.print("[yellow]⚠️ Mode switching is not available in Dify mode[/]")
                        ctx.console.print("[dim]Dify mode is a standalone cloud AI service. Use '/switch dify' to exit and switch to local LLM modes.[/]")
                        continue
                    
                    # Parse mode command
                    command, args = parse_command(query)
                    if not args:
                        current_mode = "LLM Mode" if ctx.llm_mode else "Agent Mode"
                        ctx.console.print(f"[yellow]⚠️ Usage: /mode llm/agent[/]")
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
                        ctx.console.print(f"[yellow]⚠️ {result['message']}[/]")
                    continue

                # Stream commands
                if normalized_query.lower().startswith("stream "):
                    # 在 Dify 模式下禁用流式控制命令
                    if ctx.dify_mode:
                        ctx.console.print("[yellow]⚠️ Stream control is not available in Dify mode[/]")
                        ctx.console.print("[dim]Dify mode uses built-in streaming. Use '/switch dify' to exit and switch to local LLM modes.[/]")
                        continue
                    
                    # Parse stream command (only effective in LLM mode)
                    if not ctx.llm_mode:
                        ctx.console.print("[yellow]⚠️ Streaming output is only available in LLM mode, please switch to LLM mode first[/]")
                        ctx.console.print("[dim]Use '/mode llm' to switch to LLM mode[/]")
                        continue
                        
                    command, args = parse_command(query)
                    if not args:
                        ctx.console.print("[yellow]⚠️ Usage: /stream on/off[/]")
                        ctx.console.print(f"[dim]LLM streaming output status: {'Enabled' if ctx.streaming_enabled else 'Disabled'}[/]")
                        continue

                    action = args.lower()
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
                        ctx.console.print(f"[red]❌ Agent mode processing failed: {str(e)}[/]")

            except KeyboardInterrupt:
                ctx.console.print("\n[yellow]Goodbye![/]")
                break
            except Exception as e:
                ctx.console.print(f"[bold red]Error: {e}")

    except Exception as e:
        ctx.console.print(f"[bold red]Agent initialization failed: {e}[/]")
        ctx.console.print("Please check your API keys and network connection")