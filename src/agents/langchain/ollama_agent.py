"""
Ollama Agent Implementation

基于Ollama本地模型的智能Agent实现
支持完整的工具集成和记忆功能
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.language_models import BaseChatModel

from ..llm.ollama_llm import OllamaLLM
from ..memory.global_memory import GlobalMemoryManager
from ..tools import SDKToolManager, ConnectorToolManager

logger = logging.getLogger(__name__)

# OKX工具可用性 - 通过工具管理器处理
OKX_AVAILABLE = True  # 由SDKToolManager统一管理


class OllamaAgent:
    """Ollama Agent类"""
    
    def __init__(
        self,
        model: str = "gpt-oss:20b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,  # Agent模式使用更低温度确保稳定性
        verbose: bool = False,
        enable_memory: bool = True,
        global_memory_manager = None,
        disable_thinking_mode: bool = True,  # 关闭思考模式
        **kwargs
    ):
        """
        初始化Ollama Agent
        
        Args:
            model: 模型名称
            base_url: Ollama服务地址
            temperature: 温度参数（Agent模式建议使用0.0）
            verbose: 是否显示详细信息
            enable_memory: 是否启用记忆功能
            global_memory_manager: 全局记忆管理器
            disable_thinking_mode: 是否关闭思考模式（Agent模式建议True）
            **kwargs: 其他参数
        """
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.verbose = verbose
        self.enable_memory = enable_memory
        self.global_memory_manager = global_memory_manager
        self.disable_thinking_mode = disable_thinking_mode
        self.kwargs = kwargs
        
        # 初始化组件
        self._llm = None
        self._agent = None
        self._agent_executor = None
        self._memory_manager = None
        self._tools = []
        self._initialized = False
        
        logger.info(f"创建Ollama Agent实例: {model}")
    
    async def initialize(self):
        """异步初始化Agent"""
        if self._initialized:
            return
        
        try:
            # 1. 创建LLM
            logger.info("创建Ollama LLM...")
            
            # 为Agent模式优化参数
            agent_kwargs = self.kwargs.copy()
            
            # 如果启用了思考模式禁用，添加相应参数
            if self.disable_thinking_mode:
                logger.info("已关闭思考模式以提高Agent稳定性")
                # 对于某些模型，可能需要特殊参数来禁用思考
                # 这取决于具体的模型实现
            
            ollama_llm = OllamaLLM(
                model=self.model,
                base_url=self.base_url,
                temperature=self.temperature,  # 已设置为0.0，确保稳定输出
                **agent_kwargs
            )
            
            # 健康检查
            health_ok = await ollama_llm.health_check()
            if not health_ok:
                logger.warning(f"Ollama服务检查未通过，但继续初始化")
            
            # 异步初始化
            await ollama_llm.initialize()
            self._llm = ollama_llm.create_llm()
            
            # 2. 设置工具
            logger.info("设置Agent工具...")
            await self._load_tools()
            
            # 3. 设置记忆
            if self.enable_memory:
                logger.info("设置全局记忆管理...")
                self._setup_memory()
            
            # 4. 创建Agent
            logger.info("创建ReAct Agent...")
            self._create_agent()
            
            self._initialized = True
            logger.info(f"Ollama Agent初始化完成: {self.model}")
            
        except Exception as e:
            logger.error(f"Ollama Agent初始化失败: {str(e)}")
            raise
    
    async def _load_tools(self):
        """加载所有工具"""
        self._tools = []

        # 使用SDK工具管理器获取所有SDK工具
        sdk_tools = SDKToolManager.get_all_tools()
        self._tools.extend(sdk_tools)
        logger.info(f"SDK工具加载完成: {len(sdk_tools)}个")

        # Load connector tools
        connector_manager = ConnectorToolManager()
        connector_tools = connector_manager.get_all_tools()
        self._tools.extend(connector_tools)
        logger.info(f"Connector工具加载完成: {len(connector_tools)}个")

        logger.info(f"总共加载工具: {len(self._tools)}个")

        # Append global MCP tools if available
        try:
            from ..tools.mcp import GlobalMCPManager
            await GlobalMCPManager.initialize()
            mcp_tools = GlobalMCPManager.get_tools()
            if mcp_tools:
                self._tools.extend(mcp_tools)
                logger.info(f"MCP工具加载完成: {len(mcp_tools)}个")
        except Exception:
            pass
    
    def _setup_memory(self):
        """设置记忆管理"""
        if self.global_memory_manager:
            self._memory_manager = self.global_memory_manager
        else:
            self._memory_manager = GlobalMemoryManager()
        
        logger.info("已设置全局记忆管理")
    
    def _custom_error_handler(self, error):
        """
        自定义错误处理函数，专门处理Ollama模型的常见问题
        
        Args:
            error: 解析错误信息
            
        Returns:
            str: 错误处理后的提示信息
        """
        error_msg = str(error).lower()
        
        # 502错误和模型不存在错误处理
        if "502" in error_msg or "bad gateway" in error_msg or "not found" in error_msg:
            return "遇到模型连接错误。请确保：1. Ollama服务正在运行 2. 模型已正确安装。如果问题持续，请切换到其他可用模型。"
        
        # JSON解析错误处理
        if "json" in error_msg or "parsing" in error_msg:
            return "输出格式错误，请按照以下格式重新回答：\nThought: 你的思考\nAction: 工具名称\nAction Input: 工具输入\n或者直接给出Final Answer: 最终回答"
        
        # 工具调用错误
        if "tool" in error_msg or "action" in error_msg:
            return "工具调用出错，请检查工具名称和输入格式，然后重新尝试或直接给出答案。"
        
        # 超时错误
        if "timeout" in error_msg:
            return "处理超时，请简化你的回答或直接给出Final Answer。"
        
        # LLM调用错误
        if "llm" in error_msg or "invoke" in error_msg:
            return "模型调用失败，可能是模型不可用或配置问题。请检查模型状态或切换到其他模型。"
        
        # 通用错误处理
        return f"出现错误: {str(error)}。请重新尝试或使用不同的表达方式。如果问题持续，请直接给出Final Answer。"
    
    def _create_agent(self):
        """创建Agent"""
        # 针对本地模型优化的ReAct提示词模板
        react_prompt = PromptTemplate.from_template("""
你是一个智能助手，可以回答问题并使用工具完成任务。

你可以使用以下工具：
{tools}

使用以下格式回答：

Question: 用户的问题
Thought: 你应该思考要做什么
Action: 要执行的动作，应该是[{tool_names}]中的一个
Action Input: 动作的输入
Observation: 动作执行的结果
... (这个Thought/Action/Action Input/Observation序列可以重复N次)
Thought: 我现在知道最终答案了
Final Answer: 给用户的最终回复

重要规则：
1. 必须严格按照上面的格式回答
2. Action必须是可用工具列表中的一个
3. 每次只能执行一个Action
4. 如果不需要工具，直接给出Final Answer
5. 用中文回答用户

开始！

Question: {input}
{agent_scratchpad}""")
        
        # 创建ReAct Agent（适合本地模型）
        self._agent = create_react_agent(
            llm=self._llm,
            tools=self._tools,
            prompt=react_prompt
        )
        
        # 创建Agent执行器
        # 优化配置以处理本地模型的限制和502错误
        self._agent_executor = AgentExecutor(
            agent=self._agent,
            tools=self._tools,
            verbose=self.verbose,
            handle_parsing_errors=self._custom_error_handler,  # 使用自定义错误处理器
            max_iterations=3,  # 减少迭代次数，本地模型容易出错
            max_execution_time=30,  # 缩短超时时间
            return_intermediate_steps=False
            # 移除early_stopping_method参数，使用默认值
        )
        
        # 如果启用记忆，包装为带记忆的执行器
        if self.enable_memory and self._memory_manager:
            self._agent_with_memory = RunnableWithMessageHistory(
                self._agent_executor,
                self._memory_manager.get_message_history,
                input_messages_key="input",
                history_messages_key="chat_history"
            )
        else:
            self._agent_with_memory = self._agent_executor
        
        logger.info("ReAct Agent创建完成")
    
    def invoke(self, message: str, session_id: str = "default") -> Dict[str, Any]:
        """
        同步调用Agent
        
        Args:
            message: 用户消息
            session_id: 会话ID
            
        Returns:
            Agent响应结果
        """
        if not self._initialized:
            raise RuntimeError("Agent未初始化，请先调用initialize()")
        
        try:
            if self.enable_memory:
                config = {"configurable": {"session_id": session_id}}
                result = self._agent_with_memory.invoke(
                    {"input": message},
                    config=config
                )
            else:
                result = self._agent_executor.invoke({"input": message})
            
            # 提取工具名称
            tool_names = []
            intermediate_steps = result.get("intermediate_steps", [])
            for step in intermediate_steps:
                if hasattr(step, '__len__') and len(step) >= 1:
                    # step 是 (AgentAction, observation) 元组
                    agent_action = step[0]
                    if hasattr(agent_action, 'tool'):
                        tool_names.append(agent_action.tool)
            
            return {
                "output": result.get("output", ""),
                "intermediate_steps": intermediate_steps,
                "tool_calls": len(intermediate_steps),
                "tool_names": tool_names,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Agent调用失败: {str(e)}")
            return {
                "output": f"抱歉，处理您的请求时出现错误: {str(e)}",
                "intermediate_steps": [],
                "tool_calls": 0,
                "tool_names": [],
                "success": False,
                "error": str(e)
            }
    
    async def ainvoke(self, message: str, session_id: str = "default") -> Dict[str, Any]:
        """
        异步调用Agent
        
        Args:
            message: 用户消息
            session_id: 会话ID
            
        Returns:
            Agent响应结果
        """
        if not self._initialized:
            raise RuntimeError("Agent未初始化，请先调用initialize()")
        
        try:
            if self.enable_memory:
                config = {"configurable": {"session_id": session_id}}
                result = await self._agent_with_memory.ainvoke(
                    {"input": message},
                    config=config
                )
            else:
                result = await self._agent_executor.ainvoke({"input": message})
            
            # 提取工具名称
            tool_names = []
            intermediate_steps = result.get("intermediate_steps", [])
            for step in intermediate_steps:
                if hasattr(step, '__len__') and len(step) >= 1:
                    # step 是 (AgentAction, observation) 元组
                    agent_action = step[0]
                    if hasattr(agent_action, 'tool'):
                        tool_names.append(agent_action.tool)
            
            return {
                "output": result.get("output", ""),
                "intermediate_steps": intermediate_steps,
                "tool_calls": len(intermediate_steps),
                "tool_names": tool_names,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Agent异步调用失败: {str(e)}")
            return {
                "output": f"抱歉，处理您的请求时出现错误: {str(e)}",
                "intermediate_steps": [],
                "tool_calls": 0,
                "tool_names": [],
                "success": False,
                "error": str(e)
            }
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        from ..llm.llm_manager import get_llm_info
        
        # 获取模型信息
        try:
            model_info = get_llm_info("ollama", self.model)
        except Exception as e:
            logger.warning(f"Failed to get model info: {e}")
            model_info = {}
        
        info = {
            "provider": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "tool_count": len(self._tools),
            "memory_enabled": self.enable_memory,
            "initialized": self._initialized,
            "created_at": datetime.now().isoformat(),
            # 合并模型信息
            **model_info
        }
        
        # Ollama模型不使用Model Features
        if "model_features" in info:
            del info["model_features"]
            
        return info
    
    def get_info(self) -> Dict[str, Any]:
        """获取Agent信息(兼容旧接口)"""
        return self.get_agent_info()
    
    def get_llm(self):
        """获取LLM实例（用于流式输出）"""
        if not self._initialized:
            raise RuntimeError("Agent未初始化，请先调用initialize()")
        return self._llm
    
    def clear_memory(self, session_id: str = "default"):
        """清除指定会话的记忆"""
        if self._memory_manager and self.enable_memory:
            self._memory_manager.clear_session_messages(session_id)
            logger.info(f"已清除会话 {session_id} 的记忆")
        else:
            logger.warning("记忆功能未启用")


# 构建函数
async def build_ollama_agent(
    model: str = "gpt-oss:20b",
    base_url: str = "http://localhost:11434",
    verbose: bool = False,
    temperature: float = 0.0,  # Agent模式默认使用0.0温度
    enable_memory: bool = True,
    global_memory_manager = None,
    disable_thinking_mode: bool = True,  # 默认关闭思考模式
    **kwargs
) -> OllamaAgent:
    """
    构建并初始化Ollama Agent
    
    Args:
        model: 模型名称
        base_url: Ollama服务地址
        verbose: 是否显示详细信息
        temperature: 温度参数（Agent模式建议使用0.0）
        enable_memory: 是否启用记忆功能
        global_memory_manager: 全局记忆管理器
        disable_thinking_mode: 是否关闭思考模式（Agent模式建议True）
        **kwargs: 其他参数
        
    Returns:
        初始化完成的Ollama Agent
    """
    agent = OllamaAgent(
        model=model,
        base_url=base_url,
        verbose=verbose,
        temperature=temperature,
        enable_memory=enable_memory,
        global_memory_manager=global_memory_manager,
        disable_thinking_mode=disable_thinking_mode,
        **kwargs
    )
    
    await agent.initialize()
    return agent