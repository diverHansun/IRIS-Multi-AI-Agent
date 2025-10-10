"""
智谱AI Function Calling Agent

基于智谱AI原生Function Calling API实现的Agent，支持glm-4.5和glm-4.5-flash模型。
"""

import json
import logging
import asyncio
import zhipuai
from typing import List, Dict, Any, Optional, Union
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from ....llm.langchain.instances.zhipu_llm import create_zhipu_llm
from ....components.shared.memory.global_memory import GlobalMemoryManager
from ....components.shared.tools.adapters import convert_tool_to_function, execute_tool_with_arguments, execute_tool_with_arguments_async
from ....config import settings

logger = logging.getLogger(__name__)


class ZhipuFunctionCallingAgent:
    """智谱AI Function Calling Agent"""
    
    def __init__(
        self,
        model: str = "glm-4.5-flash",
        temperature: float = 0.1,
        verbose: bool = False,
        max_iterations: int = 10,
        enable_memory: bool = True,
        global_memory_manager=None,
        **kwargs
    ):
        """
        初始化智谱AI Function Calling Agent
        
        Args:
            model: 模型名称，支持glm-4.5和glm-4.5-flash
            temperature: 温度参数
            verbose: 是否显示详细日志
            max_iterations: 最大迭代次数
            enable_memory: 是否启用记忆功能
            global_memory_manager: 全局记忆管理器
            **kwargs: 其他参数
        """
        if model not in ["glm-4.5", "glm-4.5-flash"]:
            raise ValueError("ZhipuFunctionCallingAgent仅支持glm-4.5和glm-4.5-flash模型")
        
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.enable_memory = enable_memory
        self.global_memory_manager = global_memory_manager
        self.kwargs = kwargs
        
        # 组件
        self.llm = None
        self.zhipu_client = None
        self.tools = []
        self.is_initialized = False
        
        # 记忆管理
        self.chat_memory = None
        if enable_memory:
            self._init_memory()
    
    def _init_memory(self) -> None:
        """初始化记忆管理器"""
        try:
            if self.global_memory_manager:
                self.chat_memory = self.global_memory_manager
                logger.info("使用全局记忆管理器")
            else:
                self.chat_memory = GlobalMemoryManager()
                logger.info("使用本地记忆管理器")
        except Exception as e:
            logger.error(f"记忆管理器初始化失败: {e}")
            self.enable_memory = False
    
    async def initialize(self):
        """
        初始化Agent
        """
        if self.is_initialized:
            return
        
        try:
            logger.info("开始初始化智谱AI Function Calling Agent...")
            
            # 1. 创建LLM
            self.llm = create_zhipu_llm(
                model=self.model,
                temperature=self.temperature,
                **self.kwargs
            )
            
            # 2. 创建智谱AI原生客户端（用于Function Calling）
            api_key = settings.zhipu_api_key
            if not api_key:
                raise ValueError("未找到ZHIPU_API_KEY，请检查配置")
            self.zhipu_client = zhipuai.ZhipuAI(api_key=api_key)
            
            logger.info(f"LLM初始化完成: {self.model}")
            
            # 3. 初始化工具
            await self._initialize_tools()
            
            self.is_initialized = True
            logger.info(f"智谱AI Function Calling Agent初始化完成 - 模型: {self.model}, 工具数量: {len(self.tools)}")
            
        except Exception as e:
            logger.error(f"Agent初始化失败: {e}")
            raise
    
    async def _initialize_tools(self):
        """初始化工具"""
        try:
            # 导入工具适配器中的工具获取函数
            from ....components.shared.tools.adapters.functioncalling_adapter import get_all_available_tools
            
            # 获取所有可用工具
            self.tools = get_all_available_tools()
            
            # Load connector tools
            from ...components.shared.tools import ConnectorToolManager
            connector_manager = ConnectorToolManager()
            connector_tools = connector_manager.get_all_tools()
            self.tools.extend(connector_tools)
            logger.info(f"Connector tools loaded: {len(connector_tools)} tools")
            
            # 聚合全局 MCP 工具（如 Notion MCP、Filesystem 等）
            try:
                from ...components.shared.tools.mcp import GlobalMCPManager
                await GlobalMCPManager.initialize()
                mcp_tools = GlobalMCPManager.get_tools()
                if mcp_tools:
                    self.tools.extend(mcp_tools)
                    logger.info(f"MCP 工具已加载: {len(mcp_tools)}")
                    # 记录MCP工具名称
                    mcp_tool_names = [tool.name for tool in mcp_tools]
                    logger.info(f"MCP 工具列表: {', '.join(mcp_tool_names)}")
                else:
                    logger.info("MCP 工具为空或未启用")
            except Exception as mcp_e:
                logger.error(f"MCP 工具加载失败: {mcp_e}")
                # 可以选择重新抛出异常或继续执行
                # raise  # 如果需要中断执行，可以取消注释这行
            
            logger.info(f" 已加载 {len(self.tools)} 个工具")
            if self.verbose:
                tool_names = [tool.name for tool in self.tools]
                logger.info(f"   工具列表: {', '.join(tool_names)}")
                
        except Exception as e:
            logger.error(f"工具初始化失败: {e}")
            raise
    
    async def _execute_query(self, query: str, session_id: str = "default", **kwargs) -> Dict[str, Any]:
        """
        执行查询的核心逻辑
        
        Args:
            query: 用户查询
            session_id: 会话ID
            **kwargs: 额外参数
            
        Returns:
            查询结果字典
        """
        try:
            # 获取历史对话用于上下文
            history_messages = []
            if self.enable_memory and self.chat_memory:
                history = self.chat_memory.get_session_history(session_id)
                history_messages = history.messages if history else []
            
            # 构建消息历史
            messages = []
            
            # 添加历史消息（限制数量）
            for msg in history_messages[-10:]:  # 限制最多10条历史消息
                if isinstance(msg, HumanMessage):
                    messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages.append({"role": "assistant", "content": msg.content})
                elif isinstance(msg, ToolMessage):
                    messages.append({"role": "tool", "content": msg.content, "tool_call_id": getattr(msg, "tool_call_id", "")})
            
            # 添加当前用户查询
            messages.append({"role": "user", "content": query})
            
            # 转换工具为Function Calling格式
            functions = [convert_tool_to_function(tool) for tool in self.tools]
            
            # 执行Function Calling循环
            intermediate_steps = []
            iteration = 0
            
            while iteration < self.max_iterations:
                # 添加详细的日志记录
                logger.debug(f"调用智谱AI Chat Completions API: {self.model}")
                logger.debug(f"消息历史: {messages}")
                logger.debug(f"工具列表: {functions}")
                
                # 调用智谱AI Chat Completions API
                response = self.zhipu_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=functions,
                    temperature=self.temperature
                )
                
                logger.debug(f"API响应: {response}")
                
                # 获取响应内容
                choice = response.choices[0]
                message = choice.message
                
                # 检查是否有工具调用
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    # 处理工具调用
                    tool_calls = message.tool_calls
                    tool_call_results = []
                    
                    # 添加assistant消息到历史
                    messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in tool_calls
                        ]
                    })
                    
                    # 执行所有工具调用
                    for tool_call in tool_calls:
                        tool_name = tool_call.function.name
                        tool_args_str = tool_call.function.arguments
                        
                        # 查找对应的工具
                        tool = next((t for t in self.tools if t.name == tool_name), None)
                        
                        if tool:
                            max_retries = 3
                            retry_count = 0
                            tool_result = None
                            error_msg = None
                            
                            while retry_count < max_retries:
                                try:
                                    # 解析参数
                                    tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                                    logger.debug(f"解析工具参数: {tool_args}")
                                    
                                    # 执行工具（使用异步方式）
                                    tool_result = await execute_tool_with_arguments_async(tool, tool_args)
                                    logger.debug(f"工具执行结果: {tool_result}")
                                    
                                    # 检查是否有可重试的错误
                                    if isinstance(tool_result, dict) and tool_result.get("retryable", False):
                                        retry_count += 1
                                        if retry_count < max_retries:
                                            logger.warning(f"工具 {tool_name} 执行失败，准备重试 ({retry_count}/{max_retries}): {tool_result.get('error', 'Unknown error')}")
                                            await asyncio.sleep(1)  # 等待1秒后重试
                                            continue
                                        else:
                                            logger.error(f"工具 {tool_name} 重试 {max_retries} 次后仍然失败: {tool_result.get('error', 'Unknown error')}")
                                            error_msg = tool_result
                                            break
                                    else:
                                        # 成功执行或不可重试的错误
                                        break
                                        
                                except Exception as e:
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        logger.warning(f"工具 {tool_name} 执行异常，准备重试 ({retry_count}/{max_retries}): {str(e)}")
                                        await asyncio.sleep(1)  # 等待1秒后重试
                                        continue
                                    else:
                                        logger.error(f"工具 {tool_name} 重试 {max_retries} 次后仍然异常: {str(e)}")
                                        error_msg = {"error": str(e), "type": "tool_runtime", "retryable": False, "tool_name": tool_name}
                                        break
                            
                            # 处理最终结果
                            if error_msg is None and tool_result is not None:
                                # 成功执行
                                intermediate_steps.append({
                                    "tool": tool_name,
                                    "args": tool_args,
                                    "result": tool_result,
                                    "error": None
                                })
                                
                                # 添加工具调用结果到消息历史
                                tool_result_content = json.dumps(tool_result, ensure_ascii=False) if not isinstance(tool_result, str) else tool_result
                                messages.append({
                                    "role": "tool",
                                    "content": tool_result_content,
                                    "tool_call_id": tool_call.id
                                })
                                
                                # 添加工具调用结果到工具调用结果列表
                                tool_call_results.append({
                                    "tool_call_id": tool_call.id,
                                    "content": tool_result_content
                                })
                                
                                logger.debug(f"工具调用成功: {tool_name}")
                            else:
                                # 执行失败
                                intermediate_steps.append({
                                    "tool": tool_name,
                                    "args": tool_args_str,
                                    "result": None,
                                    "error": error_msg
                                })
                                
                                error_content = json.dumps(error_msg, ensure_ascii=False)
                                messages.append({
                                    "role": "tool",
                                    "content": error_content,
                                    "tool_call_id": tool_call.id
                                })
                                
                                tool_call_results.append({
                                    "tool_call_id": tool_call.id,
                                    "content": error_content
                                })
                                
                                logger.warning(f"工具调用失败: {tool_name}, 错误: {error_msg}")
                    
                    # 增加迭代次数
                    iteration += 1
                    continue
                else:
                    # 没有工具调用，返回最终结果
                    final_answer = message.content if message.content else ""
                    
                    # 保存对话到记忆
                    if self.enable_memory and self.chat_memory:
                        self.chat_memory.add_conversation(session_id, query, final_answer)
                    
                    # 提取工具名称
                    tool_names = []
                    for step in intermediate_steps:
                        if isinstance(step, dict) and "tool" in step:
                            tool_names.append(step["tool"])
                    
                    return {
                        "output": final_answer,
                        "tool_calls": len(intermediate_steps),
                        "tool_names": tool_names,
                        "intermediate_steps": intermediate_steps,
                        "error": None,
                        "success": True
                    }
            
            # 达到最大迭代次数
            # 提取工具名称
            tool_names = []
            for step in intermediate_steps:
                if isinstance(step, dict) and "tool" in step:
                    tool_names.append(step["tool"])
            
            return {
                "output": "达到最大迭代次数，无法完成任务",
                "tool_calls": len(intermediate_steps),
                "tool_names": tool_names,
                "intermediate_steps": intermediate_steps,
                "error": "达到最大迭代次数",
                "success": False
            }
                
        except Exception as e:
            logger.error(f"查询处理失败: {e}")
            return {
                "output": "",
                "tool_calls": 0,
                "tool_names": [],
                "intermediate_steps": [],
                "error": str(e),
                "success": False
            }
    
    async def invoke(self, query: str, session_id: str = "default", **kwargs) -> Dict[str, Any]:
        """
        异步执行查询
        
        Args:
            query: 用户查询
            session_id: 会话ID
            **kwargs: 额外参数
            
        Returns:
            包含输出和中间步骤的结果字典
        """
        if not self.is_initialized:
            await self.initialize()
        
        return await self._execute_query(query, session_id, **kwargs)
    
    async def ainvoke(self, query: str, session_id: str = "default", **kwargs) -> Dict[str, Any]:
        """
        异步调用Agent（LangChain标准接口）
        
        Args:
            query: 用户查询
            session_id: 会话ID
            **kwargs: 额外参数
            
        Returns:
            包含输出和中间步骤的结果字典
        """
        return await self.invoke(query, session_id, **kwargs)
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        from ...llm.langchain.llm_manager import get_llm_info
        
        # 获取模型信息
        try:
            model_info = get_llm_info("zhipu", self.model)
        except Exception as e:
            logger.warning(f"Failed to get model info: {e}")
            model_info = {}
            
        info = {
            "provider": "zhipu",
            "model": self.model,
            "temperature": self.temperature,
            "max_iterations": self.max_iterations,
            "initialized": self.is_initialized,
            "tool_count": len(self.tools),
            "tools": [tool.name for tool in self.tools] if self.tools else [],
            "memory_enabled": self.enable_memory,
            "mode": "function_calling",  # 标识使用Function Calling模式
            # 合并模型信息
            **model_info
        }
        
        return info
    
    def get_info(self) -> Dict[str, Any]:
        """获取Agent信息(兼容旧接口)"""
        return self.get_agent_info()
    
    def get_llm(self):
        """获取底层LLM实例用于流式输出"""
        return self.llm


# 兼容性函数
async def build_zhipu_fcall_agent(
    model: str = "glm-4.5",
    verbose: bool = False,
    temperature: float = 0.1,
    **kwargs
) -> ZhipuFunctionCallingAgent:
    """
    创建并初始化智谱AI Function Calling Agent
    
    Args:
        model: 模型名称
        verbose: 是否显示详细日志
        temperature: 模型温度参数
        **kwargs: 其他参数
        
    Returns:
        初始化完成的ZhipuFunctionCallingAgent实例
    """
    agent = ZhipuFunctionCallingAgent(
        model=model,
        temperature=temperature,
        verbose=verbose,
        **kwargs
    )
    
    await agent.initialize()
    return agent