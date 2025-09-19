"""
OpenAI Agent Implementation

基于OpenAI GPT模型的智能Agent实现
支持完整的工具集成和记忆功能
"""

import logging
from typing import Dict, Any, List, Optional, Iterable
from datetime import datetime

from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.language_models import BaseChatModel

from ..llm.openai_llm import build_openai_chat, OpenAILLM
from ..memory.global_memory import GlobalMemoryManager
from ..tools.calculate.math_tools import add_numbers, calculate_math
from ..tools.search.search_tools import SEARCH_TOOLS
from ..tools.search.tavily_search_tool import get_available_tavily_tools
from ..tools.amap import get_available_amap_tools
from ..tools.time import get_available_time_tools
from ..tools.notion import get_notion_tools

# 尝试导入OKX工具（可选）
try:
    from ..tools.okx_market.langchain_tools import (
        get_crypto_price, get_market_data, get_kline_data, 
        analyze_price_trend, create_price_alert, check_price_alerts,
        get_market_summary, search_crypto_symbols
    )
    OKX_AVAILABLE = True
except ImportError:
    OKX_AVAILABLE = False

logger = logging.getLogger(__name__)


def _format_exception(e: Exception) -> str:
    """Render rich details for ExceptionGroup/TaskGroup to aid debugging."""
    try:
        if hasattr(e, "exceptions") and isinstance(getattr(e, "exceptions"), Iterable):
            parts = [f"{e.__class__.__name__}: {e}"]
            for idx, se in enumerate(getattr(e, "exceptions")):
                parts.append(f"  [{idx}] {se.__class__.__name__}: {se}")
            return "\n".join(parts)
    except Exception:
        pass
    return f"{e.__class__.__name__}: {e}"

class OpenAIAgent:
    """OpenAI Agent类"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        verbose: bool = False,
        enable_memory: bool = True,
        global_memory_manager = None,
        **kwargs
    ):
        """
        初始化OpenAI Agent
        
        Args:
            api_key: OpenAI API密钥
            model: 模型名称
            temperature: 温度参数
            verbose: 是否显示详细信息
            enable_memory: 是否启用记忆功能
            global_memory_manager: 全局记忆管理器
            **kwargs: 其他参数
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        self.enable_memory = enable_memory
        self.global_memory_manager = global_memory_manager
        self.kwargs = kwargs
        
        # 初始化组件
        self._llm = None
        self._agent = None
        self._agent_executor = None
        self._memory_manager = None
        self._tools = []
        self._initialized = False
        
        logger.info(f"创建OpenAI Agent实例: {model}")
    
    async def initialize(self):
        """异步初始化Agent"""
        if self._initialized:
            return
        
        try:
            # 1. 创建LLM
            logger.info("Creating OpenAI LLM...")
            
            # 检查是否有自定义base_url，优先级：构造函数参数 > 环境变量配置
            from ..config import settings
            base_url = self.kwargs.get('base_url') or settings.openai_base_url
            
            # 记录使用的API端点
            if base_url:
                logger.info(f"使用自定义OpenAI API端点: {base_url}")
            else:
                logger.info("使用默认OpenAI API端点")
                
            # 从kwargs中移除base_url避免重复传递
            filtered_kwargs = {k: v for k, v in self.kwargs.items() if k != 'base_url'}
            
            self._llm = build_openai_chat(
                api_key=self.api_key,
                model=self.model,
                temperature=self.temperature,
                base_url=base_url,
                **filtered_kwargs
            )
            
            # 2. 加载工具
            logger.info("Loading tools...")
            await self._load_tools()
            
            # 3. 初始化记忆系统（在创建Agent之前）
            if self.enable_memory:
                logger.info("Initializing memory system...")
                if self.global_memory_manager:
                    self._memory_manager = self.global_memory_manager
                    logger.info("Using global memory manager")
                else:
                    self._memory_manager = GlobalMemoryManager()
                    logger.info("Using local memory manager")
            
            # 4. 创建Agent
            logger.info("Creating agent...")
            await self._create_agent()
            
            self._initialized = True
            # 避免在Windows下的编码问题
            try:
                logger.info(f"OpenAI Agent initialization completed: {len(self._tools)} tools loaded")
            except UnicodeEncodeError:
                logger.info(f"OpenAI Agent初始化完成: {len(self._tools)} 个工具".encode('utf-8', errors='ignore').decode('utf-8'))
            
        except Exception as e:
            try:
                logger.error(f"OpenAI Agent initialization failed: {str(e)}")
            except UnicodeEncodeError:
                logger.error(f"OpenAI Agent初始化失败: {str(e)}".encode('utf-8', errors='ignore').decode('utf-8'))
            raise
    
    async def _load_tools(self):
        """加载所有工具"""
        self._tools = []
        
        # 数学工具
        self._tools.extend([add_numbers, calculate_math])
        
        # 搜索工具 - 优先使用Tavily
        tavily_tools = get_available_tavily_tools()
        if tavily_tools:
            self._tools.extend(tavily_tools)
            logger.info("Tavily search tools loaded")
        else:
            # 备用搜索工具
            self._tools.extend(SEARCH_TOOLS)
            logger.info("Backup search tools loaded")
        
        # 高德地图工具
        amap_tools = get_available_amap_tools()
        if amap_tools:
            self._tools.extend(amap_tools)
            logger.info("Amap tools loaded")
            
        # 时间工具
        time_tools = get_available_time_tools()
        if time_tools:
            self._tools.extend(time_tools)
            logger.info("Time tools loaded")
        
        # OKX加密货币工具（可选）
        if OKX_AVAILABLE:
            okx_tools = [
                get_crypto_price, get_market_data, get_kline_data,
                analyze_price_trend, create_price_alert, check_price_alerts,
                get_market_summary, search_crypto_symbols
            ]
            self._tools.extend(okx_tools)
            logger.info("OKX crypto tools loaded")
        
        # 添加 Notion 工具
        try:
            notion_tools = get_notion_tools()
            if notion_tools:
                self._tools.extend(notion_tools)
                logger.info(f"Notion tools loaded: {len(notion_tools)} tools")
            else:
                logger.warning("Notion tools not configured, need NOTION_TOKEN")
        except Exception as e:
            logger.warning(f"Failed to load Notion tools: {e}")
        
        logger.info(f"Total {len(self._tools)} tools loaded")
        # Append global MCP tools if available
        try:
            from ..MCP import GlobalMCPManager
            await GlobalMCPManager.initialize()
            mcp_tools = GlobalMCPManager.get_tools()
            if mcp_tools:
                self._tools.extend(mcp_tools)
                logger.info(f"MCP tools loaded: {len(mcp_tools)} tools")
        except Exception:
            pass
    
    async def _create_agent(self):
        """创建Agent和AgentExecutor"""
        
        # 根据模型选择优化的系统提示词
        if self.model.startswith("gpt-5"):
            # GPT-5系列模型的增强提示词
            system_prompt = """你是一个专业的智能AI助手，具备显著增强的推理能力和创造性思维。

## 核心能力特点
作为GPT-5模型，你具备以下增强能力：
- **高级推理**: 多步骤逻辑推理和抽象概念理解
- **增强创造**: 创新性问题解决和创意生成
- **精准工具调用**: 更智能的工具选择和参数优化
- **深度理解**: 复杂上下文和隐含意图的准确把握

## 工作原则
你能够使用各种专业工具来回答用户问题。凭借GPT-5的先进能力，你可以更智能地预测用户需求，制定更优化的解决方案。

当前时间：{current_time}"""
        else:
            # 标准的系统提示词
            system_prompt = """你是一个专业的智能AI助手，采用ReAct（推理-行动）框架进行逻辑推理和问题解决。你具备多领域专业知识，能够通过系统化的思考过程和工具使用为用户提供准确、全面的帮助。

## 工作原则
你能够使用各种专业工具来回答用户问题。当需要获取信息、进行计算或执行特定任务时，你会自动选择和调用合适的工具。

当前时间：{current_time}"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt.format(current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])
        
        # 创建OpenAI工具Agent
        self._agent = create_openai_tools_agent(
            llm=self._llm,
            tools=self._tools,
            prompt=prompt
        )
        
        # 创建AgentExecutor，在Windows环境下禁用verbose避免编码问题
        import sys
        is_windows = sys.platform.startswith('win')
        verbose_setting = False if is_windows else self.verbose
        
        # 针对GPT-5模型的特殊优化配置
        if self.model.startswith("gpt-5"):
            # GPT-5具备更强的推理能力，可以处理更复杂的任务
            max_iterations = 15  # 增加最大迭代次数
            max_execution_time = 600  # 增加执行时间到10分钟
            logger.info(f"GPT-5优化配置: max_iterations={max_iterations}, max_execution_time={max_execution_time}")
        else:
            max_iterations = 10
            max_execution_time = 300  # 5分钟超时
        
        self._agent_executor = AgentExecutor(
            agent=self._agent,
            tools=self._tools,
            verbose=verbose_setting,
            handle_parsing_errors=True,
            max_iterations=max_iterations,
            max_execution_time=max_execution_time,
        )
        
        # 如果启用记忆，包装AgentExecutor
        if self.enable_memory and self._memory_manager:
            if self.global_memory_manager:
                # 使用全局记忆管理器
                self._agent_executor = self.global_memory_manager.create_runnable_with_memory(
                    self._agent_executor,
                    input_key="input",
                    history_key="chat_history"
                )
            else:
                # 使用本地记忆管理器（向后兼容）
                self._agent_executor = RunnableWithMessageHistory(
                    self._agent_executor,
                    self._memory_manager.get_session_history,
                    input_messages_key="input",
                    history_messages_key="chat_history"
                )
    
    def invoke(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """同步调用Agent"""
        if not self._initialized:
            raise RuntimeError("Agent未初始化，请先调用initialize()")
        
        try:
            config = {"configurable": {"session_id": session_id}} if self.enable_memory else {}
            
            if self.enable_memory:
                result = self._agent_executor.invoke(
                    {"input": query},
                    config=config
                )
            else:
                result = self._agent_executor.invoke({"input": query})
            
            # 统计工具调用次数和提取工具名称
            tool_calls = 0
            tool_names = []
            if "intermediate_steps" in result:
                tool_calls = len(result["intermediate_steps"])
                # 提取工具名称
                for step in result["intermediate_steps"]:
                    if hasattr(step, '__len__') and len(step) >= 1:
                        # step 是 (AgentAction, observation) 元组
                        agent_action = step[0]
                        if hasattr(agent_action, 'tool'):
                            tool_names.append(agent_action.tool)
            
            return {
                "success": True,
                "output": result.get("output", ""),
                "tool_calls": tool_calls,
                "tool_names": tool_names,
                "session_id": session_id
            }
            
        except Exception as e:
            msg = _format_exception(e)
            try:
                logger.error(f"Agent invoke failed: {msg}")
            except UnicodeEncodeError:
                logger.error(f"Agent调用失败: {msg}".encode('utf-8', errors='ignore').decode('utf-8'))
            return {
                "success": False,
                "error": msg,
                "output": "",
                "tool_calls": 0,
                "tool_names": [],
                "session_id": session_id
            }
    
    async def ainvoke(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """异步调用Agent"""
        if not self._initialized:
            await self.initialize()
        
        try:
            config = {"configurable": {"session_id": session_id}} if self.enable_memory else {}
            
            if self.enable_memory:
                result = await self._agent_executor.ainvoke(
                    {"input": query},
                    config=config
                )
            else:
                result = await self._agent_executor.ainvoke({"input": query})
            
            # 统计工具调用次数和提取工具名称
            tool_calls = 0
            tool_names = []
            if "intermediate_steps" in result:
                tool_calls = len(result["intermediate_steps"])
                # 提取工具名称
                for step in result["intermediate_steps"]:
                    if hasattr(step, '__len__') and len(step) >= 1:
                        # step 是 (AgentAction, observation) 元组
                        agent_action = step[0]
                        if hasattr(agent_action, 'tool'):
                            tool_names.append(agent_action.tool)
            
            return {
                "success": True,
                "output": result.get("output", ""),
                "tool_calls": tool_calls,
                "tool_names": tool_names,
                "session_id": session_id
            }
            
        except Exception as e:
            msg = _format_exception(e)
            try:
                logger.error(f"Agent async invoke failed: {msg}")
            except UnicodeEncodeError:
                logger.error(f"Agent异步调用失败: {msg}".encode('utf-8', errors='ignore').decode('utf-8'))
            return {
                "success": False,
                "error": msg,
                "output": "",
                "tool_calls": 0,
                "tool_names": [],
                "session_id": session_id
            }
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        from ..llm.llm_manager import get_llm_info
        
        # 获取模型信息
        try:
            model_info = get_llm_info("openai", self.model)
        except Exception as e:
            logger.warning(f"Failed to get model info: {e}")
            model_info = {}
        
        info = {
            "provider": "openai",
            "model": self.model,
            "temperature": self.temperature,
            "initialized": self._initialized,
            "memory_enabled": self.enable_memory,
            "tool_count": len(self._tools),
            "tools": [tool.name for tool in self._tools] if self._tools else [],
            # 合并模型信息
            **model_info
        }
        
        # GPT-5特殊信息
        if self.model.startswith("gpt-5"):
            info.update({
                "model_generation": "GPT-5",
                "model_features": [
                    "高级推理能力",
                    "增强创造性思维", 
                    "精准工具调用",
                    "深度上下文理解",
                    "优化任务执行"
                ],
                "max_iterations": 15 if self.model.startswith("gpt-5") else 10,
                "max_execution_time": 600 if self.model.startswith("gpt-5") else 300,
                "architecture": "next_generation" if self.model == "gpt-5" else "optimized"
            })
        
        return info
    
    def get_info(self) -> Dict[str, Any]:
        """获取Agent信息(兼容旧接口)"""
        return self.get_agent_info()
    
    def get_llm(self):
        """获取底层LLM实例用于流式输出"""
        return self._llm
    
    # 记忆管理方法
    def clear_memory(self, session_id: str) -> bool:
        """清除指定会话的记忆"""
        if self._memory_manager:
            return self._memory_manager.clear_session(session_id)
        return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        if self._memory_manager:
            return self._memory_manager.list_sessions()
        return []
    
    def restore_session(self, session_id: str) -> bool:
        """恢复指定会话"""
        if self._memory_manager:
            # 检查会话是否存在（通过获取会话信息）
            session_info = self._memory_manager.get_session_info(session_id)
            return session_info is not None
        return False
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        if self._memory_manager:
            return self._memory_manager.get_session_info(session_id)
        return None


# 便捷构建函数
async def build_openai_agent(
    api_key: str,
    model: str = "gpt-4o-mini",
    verbose: bool = False,
    temperature: float = 0.1,
    enable_memory: bool = True,
    **kwargs
) -> OpenAIAgent:
    """
    构建OpenAI Agent
    
    Args:
        api_key: OpenAI API密钥
        model: 模型名称
        verbose: 是否显示详细信息
        temperature: 温度参数
        enable_memory: 是否启用记忆
        **kwargs: 其他参数
    
    Returns:
        初始化完成的OpenAIAgent实例
    """
    agent = OpenAIAgent(
        api_key=api_key,
        model=model,
        temperature=temperature,
        verbose=verbose,
        enable_memory=enable_memory,
        **kwargs
    )
    
    await agent.initialize()
    return agent


# 简单聊天模型构建函数
def build_simple_openai_chat(
    api_key: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.1,
    **kwargs
) -> BaseChatModel:
    """构建简单的OpenAI聊天模型（无工具）"""
    return build_openai_chat(
        api_key=api_key,
        model=model,
        temperature=temperature,
        **kwargs
    )
