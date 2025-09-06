"""
AI Agent Demo - 主程序

提供命令行交互界面和异步演示功能。
简化版本，使用新的MCP集成架构。
"""

import asyncio
from rich import print
from rich.console import Console
from rich.panel import Panel

import sys
import os
import uuid
from datetime import datetime

# 设置控制台编码
sys.stdout.reconfigure(encoding='utf-8')
# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.zhipu_agent import build_zhipu_agent, build_simple_zhipu_chat
from src.agents.agent_factory import agent_factory, create_default_agent, get_available_configurations
from src.llm.llm_manager import llm_manager
from src.llm.streaming_llm import streaming_manager, stream_llm_response
from src.llm.ollama_utils import list_ollama_models, get_model_display_info
from src.config import settings
from src.memory import GlobalMemoryManager, SessionManager
try:
    # Optional MCP manager
    from src.MCP import GlobalMCPManager
except Exception:
    GlobalMCPManager = None

console = Console()

def print_welcome():
    """打印欢迎信息"""
    welcome_text = """
多LLM智能Agent Demo

支持的功能：
• 多LLM支持 (智谱AI GLM-4-plus/GLM-4.5 OpenAI GPT-4o/4o-mini Ollama本地模型)
• 智能对话和复杂推理
• 数学计算、网络搜索、地图导航、加密货币行情
• 会话记忆和多轮对话

基本命令：
exit/quit - 退出程序
help - 查看帮助信息
info - 查看系统状态
llms - 查看可用的LLM列表
switch <provider> [model] - 切换LLM

工作模式：
mode llm - LLM模式 (流式输出，快速响应)
mode agent - Agent模式 (工具调用，推理分析)
stream on/off - 控制流式输出

记忆管理：
clear - 清除当前会话记忆
new - 创建新会话
sessions - 查看历史会话列表
restore <session_id> - 恢复指定会话
\nMCP 管理:\n
mcp status [-v]        - 查看MCP状态/服务器/工具数量\n
mcp tools [--json]     - 列出MCP工具（前缀 mcp_）\n
mcp reload             - 重新加载config/mcp.toml\n
提示: MCP 工具在Agent中以 mcp_ 前缀出现，调用时参数需为JSON对象
    """
    console.print(Panel(welcome_text, title="欢迎使用", border_style="cyan"))

def print_help():
    """打印帮助信息"""
    help_text = """
使用示例：

数学计算：
"计算 125 + 375"、"帮我算一下 15 * 23 + 100"

网络搜索：
"搜索最新的AI新闻"、"查找Python教程"

地图导航：
"搜索北京的星巴克"、"规划从天安门到故宫的步行路线"

加密货币：
"获取比特币的当前价格"、"分析比特币价格趋势"

Notion知识管理：
"在Notion中搜索项目文档"、"获取Notion最近的工作记录"

多LLM切换示例：
"switch zhipu glm-4-plus"、"switch openai gpt-4o"、"switch ollama gpt-oss:20b"

工作模式：
• LLM模式: 快速对话，支持流式输出 (默认)
• Agent模式: 完整功能，工具调用，会话记忆

流式输出：
• 仅在LLM模式下可用
• 'stream on/off' 控制启用/禁用

可用工具：
• 数学计算、网络搜索、地图导航、加密货币行情
• 详细功能请直接尝试相关问题

基本命令：
输入命令名查看具体说明 (如: 输入'llms'查看模型列表)
    """
    # 追加 MCP 指令说明
    help_text += "\nMCP 使用与指令：\n"
    help_text += "- 管理：mcp status [-v] | mcp tools [--json] | mcp reload\n"
    help_text += "- 在 Agent 中：工具名前缀为 mcp_（如 mcp_API-post-search）；Action Input 必须是单行 JSON（如 {\\\"query\\\":\\\"关键字\\\"}）。\n"
    help_text += "  示例：调用 mcp_API-post-search，参数 {\\\"query\\\":\\\"Roadmap\\\"}; 调用 mcp_API-retrieve-a-page，参数 {\\\"page_id\\\":\\\"<页面ID>\\\"}\n"
    console.print(Panel(help_text, title="帮助信息", border_style="green"))

async def print_available_llms():
    """显示可用的LLM列表（包含动态Ollama模型发现）"""
    try:
        configs = get_available_configurations()
        
        if not configs["available_providers"]:
            console.print("[red]❌ 没有可用的LLM提供商[/]")
            console.print("[yellow]请确保至少配置了一个API密钥 (ZHIPU_API_KEY 或 OPENAI_API_KEY)[/]")
            return
        
        llm_text = "可用的LLM提供商：\n\n"
        
        for provider in configs["available_providers"]:
            llm_text += f"- {provider['name']} ({provider['provider']})\n"
            llm_text += f"  默认模型: {provider['default_model']}\n"
            
            # Ollama特殊处理：显示本机可用模型和动态默认模型
            if provider['provider'] == 'ollama':
                try:
                    local_models = await list_ollama_models()
                    if local_models:
                        # 更新默认模型为本机第一个可用模型
                        llm_text = llm_text.replace(
                            f"  默认模型: {provider['default_model']}\n",
                            f"  默认模型: {local_models[0]} (Ollama list中首个模型)\n"
                        )
                        llm_text += f"  可用模型: {', '.join(local_models)}\n"
                    else:
                        # 如果没有模型，显示无可用模型
                        llm_text = llm_text.replace(
                            f"  默认模型: {provider['default_model']}\n",
                            f"  默认模型: 无 (请先安装模型)\n"
                        )
                        llm_text += "  可用模型: 无\n"
                        llm_text += "  提示: 请在终端执行 'ollama pull <model>' 安装模型\n"
                except Exception as e:
                    llm_text += f"  本机模型检测失败: {str(e)}\n"
            else:
                # 其他提供商显示静态支持的模型列表
                if "models_detail" in provider:
                    llm_text += "  支持的模型:\n"
                    for model, info in provider["models_detail"].items():
                        recommended = " [推荐]" if info.get("recommended", False) else ""
                        llm_text += f"    * {model}{recommended}: {info['description']}\n"
            
            llm_text += "\n"
        
        if configs["recommended_configs"]:
            llm_text += "推荐配置:\n"
            # 获取本机Ollama模型用于过滤推荐配置
            try:
                local_models = await list_ollama_models()
            except:
                local_models = []
            
            for rec in configs["recommended_configs"]:
                # 如果是Ollama推荐配置，只显示本机实际存在的模型
                if rec['provider_name'] == 'Ollama本地模型':
                    if rec['model'] in local_models:
                        llm_text += f"  * {rec['provider_name']} {rec['model']}: {rec['description']}\n"
                else:
                    # 其他提供商的推荐配置正常显示
                    llm_text += f"  * {rec['provider_name']} {rec['model']}: {rec['description']}\n"
        
        llm_text += f"\n启动默认LLM: {configs.get('default_config', {}).get('provider', 'N/A')} / {configs.get('default_config', {}).get('model', 'N/A')}"
        
        console.print(Panel(llm_text, title="LLM信息", border_style="blue"))
        
    except Exception as e:
        console.print(f"[red]获取LLM信息失败: {str(e)}[/]")

async def switch_llm(provider: str, model: str = None, global_memory=None) -> bool:
    """切换LLM"""
    try:
        # 验证提供商
        available_providers = [p["provider"] for p in get_available_configurations()["available_providers"]]
        if provider not in available_providers:
            console.print(f"[red]❌ 不支持的LLM提供商: {provider}[/]")
            console.print(f"[yellow]可用提供商: {', '.join(available_providers)}[/]")
            return False
        
        # 创建新Agent并传递全局记忆管理器
        console.print(f"[yellow]正在切换到 {provider} {model or '(默认模型)'}...[/]")
        
        new_agent = await agent_factory.create_agent(
            provider=provider,
            model=model,
            verbose=True,
            temperature=0.1,
            use_cache=False,  # 切换时不使用缓存
            global_memory_manager=global_memory  # 传递全局记忆管理器
        )
        
        # 获取Agent信息
        info = new_agent.get_info()
        console.print(f"[green]✅ 成功切换到 {info['provider']} / {info['model']}[/]")
        console.print(f"[dim]工具数: {info['tool_count']}, 记忆: {'启用' if info['memory_enabled'] else '禁用'}[/]")
        console.print(f"[dim]记忆已保持连续，切换后可继续之前的对话[/]")
        
        return new_agent
        
    except Exception as e:
        console.print(f"[red]❌ 切换LLM失败: {str(e)}[/]")
        return False

async def cli_async():
    """命令行交互界面（异步版，单一事件循环）"""
    # 检查至少有一个LLM可用
    configs = get_available_configurations()
    if not configs["available_providers"]:
        console.print("[bold red]错误: 没有可用的LLM提供商[/]")
        console.print("请在.env文件中设置至少一个API密钥:")
        console.print("- ZHIPU_API_KEY (智谱AI)")
        console.print("- OPENAI_API_KEY (OpenAI)")
        return

    print_welcome()

    # 初始化全局记忆管理系统
    console.print("[yellow]正在初始化记忆系统...[/]")
    global_memory = GlobalMemoryManager(storage_dir="data/sessions", max_messages=50)
    session_manager = SessionManager(global_memory)
    
    # 交互式选择会话（恢复或新建）
    session_id = session_manager.prompt_for_session_choice()
    console.print(f"[dim]当前会话ID: {session_id}[/]")
    
    # 工作模式标识
    # True: LLM模式（流式输出，直接与LLM交互）
    # False: Agent模式（完整Agent功能，包括工具调用）
    llm_mode = True  # 默认为LLM模式
    
    # 流式输出标识 (仅LLM模式支持)
    streaming_enabled = True  # LLM模式下的流式输出

    try:
        # 创建默认Agent（异步）并集成全局记忆
        with console.status("[yellow]正在初始化默认Agent...[/]"):
            base_agent = await create_default_agent(
                verbose=True,
                temperature=0.1,
                global_memory_manager=global_memory  # 传递全局记忆管理器
            )
            
            # 直接使用基础Agent
            agent = base_agent

        # 显示初始化信息
        info = agent.get_info()
        console.print(f"[green]Agent初始化完成！[/]")
        console.print(f"[dim]提供商: {info['provider']}, 模型: {info['model']}, 工具数: {info['tool_count']}[/]")
        
        # 显示当前模式和提示
        if llm_mode:
            console.print(f"[green]当前模式: LLM模式（流式输出）[/]")
            console.print(f"[dim]特点: 快速响应 | 实时显示 | 直接对话[/]")
            console.print(f"[dim]切换: 输入 'mode agent' 使用工具功能[/]")
        else:
            console.print(f"[blue]当前模式: Agent模式（工具调用）[/]")
            console.print(f"[dim]特点: 智能推理 | 工具调用 | 会话记忆[/]")
            console.print(f"[dim]切换: 输入 'mode llm' 使用快速对话[/]")

        while True:
            try:
                # 动态提示符显示当前模式
                mode_indicator = "LLM" if llm_mode else "Agent"
                stream_indicator = "[S]" if (llm_mode and streaming_enabled) else ""
                
                prompt = f"\n[bold cyan]{mode_indicator}{stream_indicator}[/] > "
                query = await asyncio.to_thread(console.input, prompt)

                if query.strip().lower() in {"exit", "quit", "退出"}:
                    console.print("[yellow]再见！[/]")
                    break

                if query.strip().lower() in {"help", "帮助"}:
                    print_help()
                    continue

                if query.strip().lower() in {"info", "信息"}:
                    info = agent.get_info()
                    llm_info = agent.get_llm_info()  # 获取LLM详细信息
                    
                    console.print(f"[bold blue]系统信息：[/]")
                    console.print(f"  LLM提供商: {info.get('provider', 'N/A')}")
                    console.print(f"  模型: {info['model']}")
                    console.print(f"  温度: {info.get('temperature', 'N/A')}")
                    console.print(f"  已初始化: {info['initialized']}")
                    
                    # 显示模型特殊信息（GLM-4.5）
                    if llm_info.get('architecture'):
                        console.print(f"  架构: {llm_info['architecture']}")
                    if llm_info.get('context_window'):
                        console.print(f"  上下文: {llm_info['context_window']}")
                    if llm_info.get('thinking_mode'):
                        console.print(f"  思考模式: [green]启用[/] ")
                    
                    # 显示当前模式
                    mode_text = "LLM模式（流式输出）" if llm_mode else "Agent模式（工具调用）"
                    console.print(f"  工作模式: {mode_text}")
                    
                    if llm_mode:
                        console.print(f"    流式输出: {'启用' if streaming_enabled else '禁用'}")
                        console.print(f"    功能特点: 快速响应，实时显示，无工具调用")
                        # 显示模型特殊功能
                        if llm_info.get('model_features'):
                            console.print(f"    模型特性: {', '.join(llm_info['model_features'])}")
                    else:
                        console.print(f"    记忆功能: {'启用' if info.get('memory_enabled', False) else '禁用'}")
                        console.print(f"    工具数量: {info['tool_count']}")
                        console.print(f"    可用工具: {', '.join(info['tools'])}")
                        console.print(f"    功能特点: 完整推理，工具调用，会话记忆")
                        # 显示模型特殊功能
                        if llm_info.get('model_features'):
                            console.print(f"    模型特性: {', '.join(llm_info['model_features'])}")
                    
                    console.print(f"  当前会话ID: {session_id}")
                    continue

                if query.strip().lower() in {"llms", "llm", "模型列表"}:
                    await print_available_llms()
                    continue

                # MCP commands
                if query.strip().lower().startswith("mcp "):
                    parts = query.strip().split()
                    sub = parts[1].lower() if len(parts) > 1 else ""
                    if sub in {"status", "tools", "reload"}:
                        if GlobalMCPManager is None:
                            console.print("[yellow]MCP 管理器不可用（缺少依赖或未集成）[/]")
                            continue
                        # ensure initialized (respect config)
                        try:
                            await GlobalMCPManager.initialize()
                        except Exception as e:
                            console.print(f"[yellow]MCP 初始化失败: {e}[/]")
                    if sub == "status":
                        verbose = any(a in ["-v", "--verbose"] for a in parts[2:])
                        status = GlobalMCPManager.get_status(verbose=verbose)
                        import json
                        if verbose:
                            console.print(Panel(json.dumps(status, ensure_ascii=False, indent=2), title="MCP Status", border_style="magenta"))
                        else:
                            servers = status.get("servers", [])
                            lines = [
                                f"启用: {status.get('enabled')}  已初始化: {status.get('initialized')}  工具数: {status.get('tools_total')}",
                                f"配置: {status.get('config_path') or 'N/A'}  最近重载: {status.get('last_reload') or 'N/A'}",
                            ]
                            for s in servers:
                                lines.append(f"- {s.get('name')}: {s.get('status')} (tools: {s.get('tools_count')})")
                            if status.get("last_error"):
                                lines.append(f"错误: {status['last_error']}")
                            console.print(Panel("\n".join(lines), title="MCP 状态", border_style="magenta"))
                        continue
                    if sub == "tools":
                        json_flag = any(a == "--json" for a in parts[2:])
                        tools = GlobalMCPManager.get_tools() if GlobalMCPManager else []
                        if json_flag:
                            data = [{"name": t.name, "description": getattr(t, "description", "") or ""} for t in tools]
                            import json
                            console.print(json.dumps(data, ensure_ascii=False, indent=2))
                        else:
                            if tools:
                                lines = [f"共 {len(tools)} 个 MCP 工具:"]
                                for t in tools[:100]:
                                    desc = getattr(t, "description", "") or ""
                                    lines.append(f"- {t.name}: {desc[:120]}")
                                if len(tools) > 100:
                                    lines.append(f"... 其余 {len(tools) - 100} 个未显示")
                                console.print(Panel("\n".join(lines), title="MCP 工具", border_style="magenta"))
                            else:
                                console.print("[yellow]当前没有可用的 MCP 工具（可能未启用或初始化失败）[/]")
                        continue
                    if sub == "reload":
                        result = await GlobalMCPManager.reload_config()
                        import json
                        console.print(Panel(json.dumps(result, ensure_ascii=False, indent=2), title="MCP 重新加载", border_style="magenta"))
                        continue
                    console.print("[yellow]用法: mcp status [-v] | mcp tools [--json] | mcp reload[/]")
                    continue

                if query.strip().lower().startswith("switch "):
                    # 解析switch命令
                    parts = query.strip().split()
                    if len(parts) < 2:
                        console.print("[yellow]⚠️ 使用格式: switch <provider> [model][/]")
                        console.print("[dim]示例: switch openai gpt-4o-mini[/]")
                        continue

                    provider = parts[1]
                    model = parts[2] if len(parts) > 2 else None

                    # Ollama特殊处理：动态模型选择和验证
                    if provider.lower() == 'ollama':
                        try:
                            local_models = await list_ollama_models()
                            
                            if not model:  # 未指定模型，自动选择
                                if not local_models:
                                    console.print("[yellow]未检测到可用的 Ollama 模型。[/]")
                                    console.print("[dim]请在终端执行: ollama pull <model> 安装模型[/]")
                                    continue
                                model = local_models[0]  # 选择第一个模型
                                console.print(f"[cyan]自动选择模型: {model}[/]")
                            else:  # 指定了模型，验证是否存在
                                if model not in local_models:
                                    console.print(f"[red]模型不存在/未下载: {model}[/]")
                                    console.print(f"[dim]请在终端执行: ollama pull {model}[/]")
                                    if local_models:
                                        console.print(f"[dim]可用模型: {', '.join(local_models)}[/]")
                                    continue
                        except Exception as e:
                            console.print(f"[red]检查Ollama模型时出错: {str(e)}[/]")
                            continue

                    # 异步切换LLM（复用同一事件循环）
                    with console.status(f"[yellow]正在切换到 {provider} {model or '(默认模型)'}...[/]"):
                        new_agent = await switch_llm(provider, model, global_memory)
                    if new_agent:
                        agent = new_agent
                    continue

                if query.strip().lower() in {"clear", "清除记忆", "重置"}:
                    if session_manager.clear_current_session():
                        console.print("[green]✅ 当前会话记忆已清除[/]")
                    else:
                        console.print("[yellow]⚠️ 记忆清除失败[/]")
                    continue

                if query.strip().lower() in {"new", "新会话", "创建会话"}:
                    old_session_id = session_id
                    session_id = session_manager.create_new_session()
                    console.print(f"[green]✅ 已创建新会话: {session_id}[/]")
                    console.print(f"[dim]原会话 {old_session_id} 已保存[/]")
                    continue

                if query.strip().lower() in {"sessions", "会话列表", "ls"}:
                    sessions = global_memory.list_sessions()
                    if sessions:
                        console.print(f"[bold blue]历史会话列表 ({len(sessions)} 个):[/]")
                        for i, session in enumerate(sessions[:10], 1):  # 显示前10个
                            created_time = session.get("created_at", "")[:19] if session.get("created_at") else "未知"
                            current_marker = " [当前]" if session['session_id'] == session_id else ""
                            console.print(f"  {i}. {session['session_id']}{current_marker} - {session['message_count']} 条消息 - {created_time}")
                        if len(sessions) > 10:
                            console.print(f"  ... 还有 {len(sessions) - 10} 个会话")
                        console.print("[dim]输入 'restore <session_id>' 恢复指定会话[/]")
                    else:
                        console.print("[yellow]暂无历史会话[/]")
                    continue

                if query.strip().lower().startswith("restore "):
                    target_session_id = query.strip()[8:].strip()
                    if target_session_id:
                        if session_manager.switch_to_session(target_session_id):
                            session_id = target_session_id
                            session_info = global_memory.get_session_info(session_id)
                            if session_info:
                                console.print(f"[green]✅ 已切换到会话: {session_id}[/]")
                                console.print(f"[dim]消息数: {session_info['message_count']} | 创建时间: {session_info.get('created_at', '')[:19]}[/]")
                                # 显示会话摘要
                                summary = session_manager.get_current_session_summary()
                                if summary != "暂无对话历史":
                                    console.print(f"[dim]会话摘要: {summary}[/]")
                            else:
                                console.print(f"[green]✅ 已切换到会话: {session_id}[/]")
                        else:
                            console.print(f"[red]❌ 会话不存在: {target_session_id}[/]")
                    else:
                        console.print("[yellow]⚠️ 请提供有效的会话ID，格式：restore <session_id>[/]")
                    continue

                if query.strip().lower().startswith("mode "):
                    # 解析mode命令
                    parts = query.strip().split()
                    if len(parts) < 2:
                        current_mode = "LLM模式" if llm_mode else "Agent模式"
                        console.print(f"[yellow]⚠️ 使用格式: mode llm/agent[/]")
                        console.print(f"[dim]当前模式: {current_mode}[/]")
                        continue

                    mode = parts[1].lower()
                    if mode in ["llm", "流式", "stream"]:
                        llm_mode = True
                        streaming_enabled = True
                        console.print("[green]已切换到LLM模式（流式输出）[/]")
                        console.print("[dim]特点: 快速响应 | 实时显示 | 直接对话[/]")
                        console.print("[dim]适用: 日常聊天、文本生成、快速问答[/]")
                    elif mode in ["agent", "代理", "工具"]:
                        llm_mode = False
                        console.print("[blue]已切换到Agent模式（工具调用）[/]")
                        console.print("[dim]特点: 智能推理 | 工具调用 | 会话记忆[/]")
                        console.print("[dim]适用: 搜索查询、计算分析、复杂任务[/]")
                    else:
                        console.print("[yellow]⚠️ 无效模式，请使用 llm 或 agent[/]")
                    continue

                if query.strip().lower().startswith("stream "):
                    # 解析stream命令（仅在LLM模式下有效）
                    if not llm_mode:
                        console.print("[yellow]⚠️ 流式输出仅在LLM模式下可用，请先切换到LLM模式[/]")
                        console.print("[dim]使用 'mode llm' 切换到LLM模式[/]")
                        continue
                        
                    parts = query.strip().split()
                    if len(parts) < 2:
                        console.print("[yellow]⚠️ 使用格式: stream on/off[/]")
                        console.print(f"[dim]LLM流式输出状态: {'启用' if streaming_enabled else '禁用'}[/]")
                        continue

                    action = parts[1].lower()
                    if action in ["on", "enable", "启用", "开启"]:
                        streaming_enabled = True
                        console.print("[green]✅ LLM流式输出已启用[/]")
                    elif action in ["off", "disable", "禁用", "关闭"]:
                        streaming_enabled = False
                        console.print("[yellow]⚠️ LLM流式输出已禁用[/]")
                    else:
                        console.print("[yellow]⚠️ 无效参数，请使用 on 或 off[/]")
                    continue

                if not query.strip():
                    continue

                # 根据工作模式处理查询
                if llm_mode:
                    # LLM模式：直接与LLM交互，支持流式输出和记忆功能
                    try:
                        # 导入必要的消息类型
                        from langchain_core.messages import HumanMessage, AIMessage
                        
                        # 获取Agent的LLM信息
                        info = agent.get_info()
                        provider = info.get('provider', 'unknown')
                        
                        if streaming_enabled:
                            # 流式输出模式（带记忆）
                            if hasattr(agent, 'get_llm') and callable(getattr(agent, 'get_llm')):
                                llm = agent.get_llm()
                                # 注册流式LLM
                                streaming_manager.register_llm(provider, llm)
                                
                                # 获取历史对话用于上下文
                                history = global_memory.get_session_history(session_id)
                                context_messages = history.messages[-10:] if history.messages else []
                                
                                # 构建包含历史的提示
                                full_prompt = query
                                if context_messages:
                                    context_text = "\n".join([f"{'用户' if isinstance(msg, HumanMessage) else 'AI'}: {msg.content}" for msg in context_messages[-6:]])
                                    full_prompt = f"历史对话:\n{context_text}\n\n当前问题: {query}"
                                
                                # 执行流式输出
                                console.print(f"[dim]LLM流式生成中...[/]")
                                answer = await stream_llm_response(
                                    provider=provider,
                                    prompt=full_prompt,
                                    llm=llm,
                                    display_title=f"LLM回复 ({provider})",
                                    show_display=True
                                )
                                
                                # 保存对话到记忆
                                global_memory.add_llm_conversation(session_id, query, answer)
                                
                            else:
                                console.print("[red]❌ 无法获取LLM实例[/]")
                                continue
                        else:
                            # 非流式LLM模式（带记忆）
                            llm = agent.get_llm()
                            
                            # 获取历史对话用于上下文
                            history = global_memory.get_session_history(session_id)
                            context_messages = history.messages[-10:] if history.messages else []
                            
                            # 构建包含历史的提示
                            full_prompt = query
                            if context_messages:
                                context_text = "\n".join([f"{'用户' if isinstance(msg, HumanMessage) else 'AI'}: {msg.content}" for msg in context_messages[-6:]])
                                full_prompt = f"历史对话:\n{context_text}\n\n当前问题: {query}"
                            
                            with console.status("[dim]LLM思考中...[/]"):
                                response = await llm.ainvoke([HumanMessage(content=full_prompt)])
                                answer = response.content if hasattr(response, 'content') else str(response)
                            
                            console.print(f"[bold green]LLM >[/] {answer}")
                            
                            # 保存对话到记忆
                            global_memory.add_llm_conversation(session_id, query, answer)
                                
                    except Exception as e:
                        console.print(f"[red]❌ LLM模式处理失败: {str(e)}[/]")
                        
                else:
                    # Agent模式：完整的Agent功能，包括工具调用和记忆（不支持流式输出）
                    try:
                        with console.status("[dim]Agent推理中...[/]"):
                            result = await agent.ainvoke(query, session_id=session_id)

                        if result.get("success"):
                            answer = result.get("output", "抱歉，我无法回答这个问题。")
                            console.print(f"[bold blue]Agent >[/] {answer}")

                            # 显示工具调用信息
                            if result.get("tool_calls", 0) > 0:
                                console.print(f"[dim]使用了 {result['tool_calls']} 次工具调用[/]")
                            
                            # Agent模式的对话会自动通过RunnableWithMessageHistory保存记忆
                            # 这里不需要手动保存，因为Agent已经集成了全局记忆管理器
                            
                        else:
                            console.print(f"[bold red]Agent错误: {result.get('error', '未知错误')}[/]")
                            
                    except Exception as e:
                        console.print(f"[red]❌ Agent模式处理失败: {str(e)}[/]")

            except KeyboardInterrupt:
                console.print("\n[yellow]再见！[/]")
                break
            except Exception as e:
                console.print(f"[bold red]错误: {e}")

    except Exception as e:
        console.print(f"[bold red]Agent初始化失败: {e}[/]")
        console.print("请检查您的API密钥和网络连接")

async def async_demo():
    """异步使用示例 - 演示多LLM功能"""
    console.print("[bold blue]Multi-LLM Async Demo[/]")
    
    # 检查可用的LLM
    configs = get_available_configurations()
    if not configs["available_providers"]:
        console.print("[bold red]错误: 没有可用的LLM提供商[/]")
        return
    
    try:
        console.print(f"[blue]可用的LLM提供商: {', '.join([p['provider'] for p in configs['available_providers']])}")
        
        # 演示每个可用的LLM
        for provider_info in configs["available_providers"]:
            provider = provider_info["provider"]
            default_model = provider_info["default_model"]
            
            console.print(f"\n[bold cyan]🔸 测试 {provider_info['name']} ({provider}/{default_model})[/]")
            
            try:
                # 创建Agent
                agent = await agent_factory.create_agent(
                    provider=provider,
                    model=default_model,
                    verbose=False,
                    use_cache=False
                )
                
                # 测试数学计算
                console.print("   📊 Testing math calculation...")
                result = await agent.ainvoke("计算 123 + 456")
                console.print(f"   Math: {result['output'][:80]}...")
                
                # 测试简单对话
                console.print("   💬 Testing conversation...")
                result = await agent.ainvoke("请用一句话介绍人工智能")
                console.print(f"   AI: {result['output'][:80]}...")
                
                # 如果有搜索工具，测试搜索功能
                info = agent.get_info()
                if any("search" in tool.lower() for tool in info.get("tools", [])):
                    console.print("   🔍 Testing search function...")
                    result = await agent.ainvoke("搜索最新的AI新闻", session_id="demo_search")
                    console.print(f"   Search: {result['output'][:80]}...")
                
                console.print(f"   ✅ {provider_info['name']} 测试完成")
                
            except Exception as e:
                console.print(f"   ❌ {provider_info['name']} 测试失败: {str(e)}")
        
        # 演示LLM切换
        console.print(f"\n[bold magenta]🔄 演示LLM切换功能[/]")
        if len(configs["available_providers"]) > 1:
            first_provider = configs["available_providers"][0]["provider"]
            second_provider = configs["available_providers"][1]["provider"]
            
            console.print(f"   切换从 {first_provider} 到 {second_provider}")
            
            agent1 = await agent_factory.create_agent(provider=first_provider)
            result1 = await agent1.ainvoke("你是什么模型？")
            console.print(f"   {first_provider}: {result1['output'][:60]}...")
            
            agent2 = await agent_factory.create_agent(provider=second_provider)
            result2 = await agent2.ainvoke("你是什么模型？")
            console.print(f"   {second_provider}: {result2['output'][:60]}...")
        else:
            console.print("   需要至少2个LLM提供商才能演示切换功能")
        
        console.print("\n[green]✅ Multi-LLM异步演示完成[/]")
        
    except Exception as e:
        console.print(f"[red]异步演示失败: {e}[/]")

def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "async":
        asyncio.run(async_demo())
    else:
        # 统一使用单一事件循环的异步CLI
        asyncio.run(cli_async())

if __name__ == "__main__":
    # 运行主程序
    main()
