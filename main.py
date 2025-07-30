"""
智谱AI Agent Demo - 主程序

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
from src.config import settings

console = Console()

def print_welcome():
    """打印欢迎信息"""
    welcome_text = """
智谱AI Agent Demo (Tavily搜索 + 高德地图集成版)

支持的功能：
• 智能对话
• 数学计算 (add_numbers, calculate_math)
• 网络搜索 (Tavily搜索 + DuckDuckGo备用)
• 高德地图搜索和导航 (地点搜索、路线规划)
• 复杂推理和多轮对话

输入 'exit' 或 'quit' 退出
输入 'help' 查看帮助信息
输入 'info' 查看Agent信息
输入 'clear' 清除当前会话记忆
输入 'sessions' 查看历史会话列表
输入 'restore <session_id>' 恢复指定会话
    """
    console.print(Panel(welcome_text, title="欢迎使用", border_style="cyan"))

def print_help():
    """打印帮助信息"""
    help_text = """
使用说明：

1. 直接输入问题进行对话
2. 数学计算问题：
   "计算 125 + 375"  
   "帮我算一下 15 * 23 + 100"
   "计算 sin(pi/4) + sqrt(16)"
3. 网络搜索问题：
   "搜索最新的AI新闻"
   "查找Python教程"
   "搜索人工智能发展趋势"
4. 高德地图查询：
   "搜索北京的星巴克"
   "查找天安门附近的酒店"
   "规划从上海世博展览馆到东方明珠的驾车路线"
   "规划从天安门到故宫的步行路线"
   "规划从北京站到首都机场的公共交通路线"
   "规划从天安门到故宫的地铁路线"
   "规划从北京站到王府井的公交路线"
5. 支持复杂的推理和分析任务

可用工具：
• 数学工具：简单加法、一般运算
• 搜索工具：Tavily搜索、DuckDuckGo搜索、网页内容获取
• 高德地图工具：地点搜索、附近搜索、驾车导航、步行导航、公共交通、地铁规划、公交规划

搜索功能：
• 优先使用Tavily搜索（高质量AI搜索）
• 自动降级到DuckDuckGo搜索作为备用
• 支持基础搜索、高级搜索、新闻搜索等

高德地图功能：
• 地点搜索：搜索商店、景点、服务设施等
• 附近搜索：查找指定位置周围的POI
• 城市搜索：在指定城市内搜索地点
• 驾车导航：规划最优驾车路线
• 步行导航：规划步行路线
• 公共交通：规划公交、地铁、火车等综合路线
• 地铁规划：优先使用地铁的路线规划
• 公交规划：只使用公交车的路线规划

记忆功能：
• 每次启动生成新的会话ID，避免历史对话干扰
• 输入 'clear' 可清除当前会话记忆
• 输入 'info' 可查看当前会话ID
• 输入 'sessions' 查看所有历史会话列表
• 输入 'restore <session_id>' 恢复指定会话的记忆
    """
    console.print(Panel(help_text, title="帮助信息", border_style="green"))

def cli():
    """命令行交互界面"""
    if not settings.zhipu_api_key:
        console.print("[bold red]错误: 未设置ZHIPU_API_KEY环境变量[/]")
        console.print("请在.env文件中设置您的智谱AI API密钥")
        return
    
    print_welcome()
    
    # 生成唯一会话ID
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    console.print(f"[dim]会话ID: {session_id}[/]")
    
    # 记忆恢复模式标识
    memory_restored = False
    
    try:
        # 创建智谱AI代理
        console.print("[yellow]正在初始化智谱AI代理...[/]")
        
        # 使用同步方式运行异步初始化
        agent = asyncio.run(build_zhipu_agent(
            model="glm-4-plus",
            verbose=True,
            temperature=0.1
        ))
        
        # 显示初始化信息
        info = agent.get_info()
        console.print(f"[green]代理初始化完成！[/]")
        console.print(f"[dim]模型: {info['model']}, 工具数: {info['tool_count']}[/]")
        
        while True:
            try:
                query = console.input("\n[bold cyan]你[/] > ")
                
                if query.strip().lower() in {"exit", "quit", "退出"}:
                    console.print("[yellow]再见！[/]")
                    break
                    
                if query.strip().lower() in {"help", "帮助"}:
                    print_help()
                    continue
                
                if query.strip().lower() in {"info", "信息"}:
                    info = agent.get_info()
                    console.print(f"[bold blue]Agent信息：[/]")
                    console.print(f"  模型: {info['model']}")
                    console.print(f"  温度: {info['temperature']}")
                    console.print(f"  已初始化: {info['initialized']}")
                    console.print(f"  工具数量: {info['tool_count']}")
                    console.print(f"  可用工具: {', '.join(info['tools'])}")
                    console.print(f"  当前会话ID: {session_id}")
                    continue
                
                if query.strip().lower() in {"clear", "清除记忆", "重置"}:
                    if agent.clear_memory(session_id):
                        console.print("[green]✅ 当前会话记忆已清除[/]")
                    else:
                        console.print("[yellow]⚠️ 记忆清除失败或未启用记忆功能[/]")
                    continue
                
                if query.strip().lower() in {"sessions", "会话列表", "ls"}:
                    sessions = agent.list_sessions()
                    if sessions:
                        console.print(f"[bold blue]📋 历史会话列表 ({len(sessions)} 个):[/]")
                        for i, session in enumerate(sessions[:10], 1):  # 显示前10个
                            created_time = session.get("created_at", "")[:19] if session.get("created_at") else "未知"
                            console.print(f"  {i}. {session['session_id']} - {session['message_count']} 条消息 - {created_time}")
                        if len(sessions) > 10:
                            console.print(f"  ... 还有 {len(sessions) - 10} 个会话")
                        console.print("[dim]输入 'restore <session_id>' 恢复指定会话[/]")
                    else:
                        console.print("[yellow]📋 暂无历史会话[/]")
                    continue
                
                if query.strip().lower().startswith("restore "):
                    target_session_id = query.strip()[8:].strip()
                    if target_session_id:
                        if agent.restore_session(target_session_id):
                            session_id = target_session_id
                            memory_restored = True
                            session_info = agent.get_session_info(session_id)
                            if session_info:
                                console.print(f"[green]✅ 已恢复会话记忆: {session_id}[/]")
                                console.print(f"[dim]消息数: {session_info['message_count']} | 创建时间: {session_info.get('created_at', '')[:19]}[/]")
                            else:
                                console.print(f"[green]✅ 已恢复会话记忆: {session_id}[/]")
                        else:
                            console.print(f"[red]❌ 会话不存在: {target_session_id}[/]")
                    else:
                        console.print("[yellow]⚠️ 请提供有效的会话ID，格式：restore <session_id>[/]")
                    continue
                
                if not query.strip():
                    continue
                
                # 调用代理处理问题
                console.print("[dim]正在思考...[/]")
                result = agent.invoke(query, session_id=session_id)
                
                if result["success"]:
                    answer = result.get("output", "抱歉，我无法回答这个问题。")
                    console.print(f"[bold green]智谱AI >[/] {answer}")
                    
                    # 显示工具调用信息
                    if result.get("tool_calls", 0) > 0:
                        console.print(f"[dim]使用了 {result['tool_calls']} 次工具调用[/]")
                    
                    # 显示记忆状态
                    if memory_restored:
                        console.print(f"[dim]💾 已恢复会话记忆模式[/]")
                else:
                    console.print(f"[bold red]错误: {result.get('error', '未知错误')}[/]")
                
            except KeyboardInterrupt:
                console.print("\n[yellow]再见！[/]")
                break
            except Exception as e:
                console.print(f"[bold red]错误: {e}[/]")
                
    except Exception as e:
        console.print(f"[bold red]代理初始化失败: {e}[/]")
        console.print("请检查您的API密钥和网络连接")

async def async_demo():
    """异步使用示例"""
    console.print("[bold blue]Async Demo[/]")
    
    if not settings.zhipu_api_key:
        console.print("[bold red]错误: 未设置ZHIPU_API_KEY环境变量[/]")
        return
    
    try:
        # 演示简单的LLM调用
        console.print("\n1. 简单LLM调用演示:")
        llm = build_simple_zhipu_chat(model="glm-4-plus", temperature=0.1)
        response = await llm.ainvoke("请用一句话介绍人工智能")
        console.print(f"[green]LLM Response:[/] {response.content}")
        
        # 演示Agent异步调用
        console.print("\n2. Agent Async Demo:")
        agent = await build_zhipu_agent(verbose=False)
        
        # 测试数学计算
        console.print("   Testing math calculation...")
        result = await agent.ainvoke("计算 42 + 58")
        console.print(f"   Math result: {result['output']}")
        
        # 测试搜索功能
        console.print("   Testing search function...")
        result = await agent.ainvoke("搜索Python教程")
        console.print(f"   Search result: {result['output'][:100]}...")
        
        console.print("\nAsync demo completed")
        
    except Exception as e:
        console.print(f"[red]异步调用失败: {e}[/]")

def main():
    """主函数"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "async":
        asyncio.run(async_demo())
    else:
        cli()

if __name__ == "__main__":
    # 运行主程序
    main()