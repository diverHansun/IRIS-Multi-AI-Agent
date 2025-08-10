"""
智谱AI代理模块

基于LangChain的ReAct Agent实现，集成MCP搜索和数学工具。
简化版本，移除复杂的多类型Agent系统。
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, Callable
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
import threading
import time

from ..llm.zhipu_llm import create_zhipu_llm
from ..tools.math_tools import add_numbers, calculate_math
from ..tools.search_tools import SEARCH_TOOLS
from ..tools.tavily_search_tool import get_available_tavily_tools
from ..tools.amap_search import get_available_amap_tools
from ..tools.okx_market import get_available_okx_tools
from ..memory.global_memory import GlobalMemoryManager
from langchain_core.runnables.history import RunnableWithMessageHistory

logger = logging.getLogger(__name__)

# GLM-4.5优化的ReAct提示模板（兼容LangChain标准解析器）
REACT_PROMPT_GLM45 = """你是Hansun的AI助手，采用ReAct框架进行推理和精确工具调用。

可用工具:
{tools}

工具清单: {tool_names}

严格使用以下增强ReAct格式：

Question: 用户的问题
Thought: 深度分析问题，制定完整解决策略
  1. 问题分析：深度解构问题层面和隐含需求
  2. 策略制定：制定主路径和备用方案
  3. 工具规划：分析所需工具序列和预期结果
Action: 选择最优工具（必须从工具清单选择）
Action Input: 精确的工具输入参数
Observation: 工具执行结果和数据分析
Reflection: 评估结果质量，判断是否需要调整策略
... (根据需要重复 Thought/Action/Action Input/Observation/Reflection)
Thought: 综合所有信息进行最终深度分析
Final Answer: 完整、准确、结构化的专业答案

核心要求：
1. Action必须严格从工具清单选择: {tool_names}
2. Action Input必须是字符串格式，避免换行符
3. 充分利用深度思考能力进行多层推理
4. 必须基于工具真实结果，禁止编造信息

常用工具说明：
- tavily_search: 通用搜索，适合大部分查询
- calculate_math: 数学计算，输入表达式
- add_numbers: 数字加法，格式"数字1 + 数字2"
- amap_search_place: 地点搜索，输入关键词
- amap_route_driving: 驾车路线，格式"起点,终点"
- get_crypto_price: 加密货币价格，输入符号如"BTC"

现在开始：

Question: {input}
Thought: {agent_scratchpad}
"""

# 优化的ReAct提示模板（兼容LangChain标准解析器）
REACT_PROMPT_ZH = """你是一个专业的智能AI助手，采用ReAct（推理-行动）框架进行逻辑推理和问题解决。

可用工具:
{tools}

工具清单: {tool_names}

严格使用以下ReAct格式：

Question: 用户的问题
Thought: 分析问题，制定解决策略
Action: 选择工具名称（必须从工具清单中选择）
Action Input: 工具的输入参数
Observation: 工具执行结果
... (根据需要重复 Thought/Action/Action Input/Observation)
Thought: 基于观察结果得出结论
Final Answer: 最终答案

核心要求：
1. Action必须严格从工具清单选择: {tool_names}
2. Action Input必须是字符串格式，避免换行符
3. 必须基于工具返回的真实结果回答，禁止编造信息
4. 每次只执行一个Action，基于Observation决定下一步

常用工具说明：
- tavily_search: 通用搜索，适合大部分查询
- calculate_math: 数学计算，输入表达式
- add_numbers: 数字加法，格式"数字1 + 数字2"
- amap_search_place: 地点搜索，输入关键词
- amap_route_driving: 驾车路线，格式"起点,终点"
- get_crypto_price: 加密货币价格，输入符号如"BTC"

现在开始：

Question: {input}
Thought: {agent_scratchpad}"""


class ZhipuAgent:
    """简化的智谱AI Agent - 支持中断功能"""
    
    def __init__(self, 
                 model: str = "glm-4-plus",
                 temperature: float = 0.1,
                 verbose: bool = False,
                 max_iterations: int = 10,
                 enable_memory: bool = True,
                 memory_config: Optional[Dict[str, Any]] = None,
                 global_memory_manager = None,
                 execution_timeout: Optional[float] = None):
        """
        初始化智谱AI Agent
        
        Args:
            model: 智谱AI模型名称
            temperature: 温度参数
            verbose: 是否显示详细日志
            max_iterations: 最大迭代次数
            enable_memory: 是否启用记忆功能
            memory_config: 记忆配置参数
            global_memory_manager: 全局记忆管理器
            execution_timeout: 执行超时时间（秒），None表示不设置超时
        """
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.enable_memory = enable_memory
        self.global_memory_manager = global_memory_manager
        self.execution_timeout = execution_timeout
        
        # 组件
        self.llm = None
        self.tools = []
        self.agent_executor = None
        self.is_initialized = False
        
        # 中断控制
        self.interruptible_executor = None
        self._progress_callback: Optional[Callable] = None
        
        # 记忆管理
        self.chat_memory = None
        self.agent_with_memory = None
        if enable_memory:
            self._init_memory(memory_config or {})
    
    async def initialize(self):
        """
        初始化Agent - 公开接口
        """
        if self.is_initialized:
            return
        
        try:
            logger.info("开始初始化智谱AI Agent...")
            
            # 1. 创建LLM
            llm_config = {
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": 2048  # 默认值
            }
            
            # GLM-4.5特殊优化
            if self.model == "glm-4.5":
                llm_config.update({
                    "max_tokens": 8192,  # GLM-4.5支持更大输出
                    "thinking_mode": True,  # 启用深度思考模式
                })
                logger.info("GLM-4.5检测：启用深度思考模式和大输出token配置")
            
            self.llm = create_zhipu_llm(**llm_config)
            logger.info(f"LLM初始化完成: {self.model}")
            
            # 2. 初始化Agent
            await self._initialize_agent()
            
            self.is_initialized = True
            logger.info(f"智谱AI Agent初始化完成 - 模型: {self.model}, 工具数量: {len(self.tools)}")
            
        except Exception as e:
            logger.error(f"Agent初始化失败: {e}")
            raise
    
    def _init_memory(self, config: Dict[str, Any]) -> None:
        """初始化记忆管理器"""
        try:
            if self.global_memory_manager:
                # 使用全局记忆管理器
                self.chat_memory = self.global_memory_manager
                logger.info("使用全局记忆管理器")
            else:
                # 使用本地GlobalMemoryManager（向后兼容）
                self.chat_memory = GlobalMemoryManager(
                    storage_dir=config.get("storage_path", "data/sessions"),
                    max_messages=config.get("max_messages", 50)
                )
                logger.info("使用本地记忆管理器")
        except Exception as e:
            logger.error(f"记忆管理器初始化失败: {e}")
            self.enable_memory = False
        
    async def _initialize_agent(self):
        """
        初始化具体的Agent实现
        """
        try:
            # 1. 收集工具
            self._collect_tools()
            
            # 2. 创建Agent
            self._build_agent()
            
            # 3. 创建带记忆的Agent（如果启用记忆）
            if self.enable_memory and self.chat_memory:
                self._build_agent_with_memory()
            
            logger.info(f"智谱AI Agent初始化完成 - 工具数量: {len(self.tools)}")
            
        except Exception as e:
            logger.error(f"Agent初始化失败: {e}")
            raise
    
    def _collect_tools(self):
        """收集所有可用工具"""
        # 清空工具列表  
        self.tools = []
        
        # 添加数学工具
        self.tools.extend([add_numbers, calculate_math])
        logger.info(f"✅ 已加载数学工具: {len([add_numbers, calculate_math])} 个")
        
        # 添加Tavily搜索工具（优先）
        tavily_tools = get_available_tavily_tools()
        if tavily_tools:
            self.tools.extend(tavily_tools)
            logger.info(f"✅ 已加载 Tavily 搜索工具: {len(tavily_tools)} 个")
        else:
            logger.warning("⚠️ Tavily 搜索工具未配置，将使用备用搜索工具")
        
        # 添加备用搜索工具（DuckDuckGo等）
        if SEARCH_TOOLS:
            self.tools.extend(SEARCH_TOOLS)
            logger.info(f"✅ 已加载备用搜索工具: {len(SEARCH_TOOLS)} 个")
        
        # 添加高德地图工具
        amap_tools = get_available_amap_tools()
        if amap_tools:
            self.tools.extend(amap_tools)
            logger.info(f"✅ 已加载高德地图工具: {len(amap_tools)} 个")
        else:
            logger.warning("⚠️ 高德地图工具未配置，需要设置 AMAP_API_KEY")
        
        # 添加OKX加密货币行情工具
        okx_tools = get_available_okx_tools()
        if okx_tools:
            self.tools.extend(okx_tools)
            logger.info(f"✅ 已加载OKX加密货币工具: {len(okx_tools)} 个")
        else:
            logger.warning("⚠️ OKX加密货币工具加载失败")
        
        logger.info(f"📋 总共收集到 {len(self.tools)} 个工具")
    
    def _build_agent(self):
        """构建Agent执行器，根据模型选择优化的提示词"""
        try:
            # 确保LLM已经初始化
            if not self.llm:
                raise ValueError("LLM未正确初始化，无法构建Agent")
            
            # 根据模型选择最优化的提示模板
            if self.model == "glm-4.5":
                prompt_template = REACT_PROMPT_GLM45
                logger.info("使用GLM-4.5优化提示词模板")
            else:
                prompt_template = REACT_PROMPT_ZH
                logger.info("使用标准ReAct提示词模板")
            
            # 创建提示模板
            prompt = PromptTemplate.from_template(prompt_template)
            
            # 创建ReAct Agent（self.llm直接就是LangChain模型）
            agent = create_react_agent(self.llm, self.tools, prompt)
            
            # 为GLM-4.5优化Agent执行器配置
            executor_config = {
                "agent": agent,
                "tools": self.tools,
                "verbose": self.verbose,
                "handle_parsing_errors": True,
                "max_iterations": self.max_iterations,
                "early_stopping_method": "force",
                "return_intermediate_steps": True
            }
            
            # GLM-4.5特殊优化：允许更多迭代以充分发挥深度思考能力
            if self.model == "glm-4.5":
                executor_config.update({
                    "max_iterations": max(self.max_iterations, 15),  # GLM-4.5可以处理更复杂的推理链
                    "max_execution_time": 180,  # 允许更长的执行时间用于深度思考
                })
                logger.info("GLM-4.5优化：增加最大迭代次数和执行时间")
            
            # 创建Agent执行器
            self.agent_executor = AgentExecutor(**executor_config)
            
            logger.info("✅ Agent执行器创建完成")
            
        except Exception as e:
            logger.error(f"❌ Agent构建失败: {e}")
            raise
    
    def _build_agent_with_memory(self):
        """构建带记忆的Agent执行器"""
        try:
            if not self.agent_executor:
                raise ValueError("基础Agent必须先初始化")
            
            if self.global_memory_manager:
                # 使用全局记忆管理器创建带记忆的Runnable
                self.agent_with_memory = self.global_memory_manager.create_runnable_with_memory(
                    self.agent_executor,
                    input_key="input",
                    history_key="chat_history"
                )
            else:
                # 使用本地GlobalMemoryManager（向后兼容）
                self.agent_with_memory = self.chat_memory.create_runnable_with_memory(
                    self.agent_executor
                )
            
            logger.info("✅ 带记忆的Agent执行器创建完成")
            
        except Exception as e:
            logger.error(f"❌ 带记忆的Agent构建失败: {e}")
            self.enable_memory = False
            raise
    
    async def _execute_query(self, query: str, session_id: str = "default", **kwargs) -> Dict[str, Any]:
        """
        执行查询的核心逻辑
        
        Args:
            query: 用户查询
            session_id: 会话 ID
            **kwargs: 额外参数
            
        Returns:
            查询结果字典
        """
        try:
            # 发送思考事件
            await self._emit_thinking_event("开始分析用户查询...")
            
            # 使用带记忆的Agent（如果启用记忆）
            if self.enable_memory and self.agent_with_memory:
                # 使用RunnableWithMessageHistory标准接口
                result = await self.agent_with_memory.ainvoke(
                    {"input": query},
                    config={"configurable": {"session_id": session_id}}
                )
                
                # 保存会话到存储
                if self.chat_memory:
                    self.chat_memory.save_session(session_id)
                
                return {
                    "output": result["output"],
                    "intermediate_steps": result.get("intermediate_steps", []),
                    "success": True,
                    "tool_calls": len(result.get("intermediate_steps", [])),
                    "session_id": session_id,
                    "memory_enabled": True
                }
            else:
                # 使用无记忆的Agent
                result = await self.agent_executor.ainvoke({"input": query})
                
                return {
                    "output": result["output"],
                    "intermediate_steps": result.get("intermediate_steps", []),
                    "success": True,
                    "tool_calls": len(result.get("intermediate_steps", [])),
                    "session_id": None,
                    "memory_enabled": False
                }
            
        except Exception as e:
            logger.error(f"查询处理失败: {e}")
            raise
    
    def invoke_sync(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """
        同步执行查询（兼容旧接口）
        
        Args:
            query: 用户查询
            session_id: 会话ID，用于记忆管理
            
        Returns:
            包含输出和中间步骤的结果
        """
        import asyncio
        
        # 使用异步invoke实现
        try:
            loop = asyncio.get_running_loop()
            # 在异步环境中，需要创建新任务
            task = asyncio.create_task(self.invoke(query, session_id))
            # 注意：这可能会导致阻塞，建议使用异步版本
            return asyncio.run_coroutine_threadsafe(task, loop).result()
        except RuntimeError:
            # 在同步环境中
            return asyncio.run(self.invoke(query, session_id))
    
    async def invoke(self, query: str, session_id: str = "default", **kwargs) -> Dict[str, Any]:
        """
        异步执行查询（主要接口）
        
        Args:
            query: 用户查询
            session_id: 会话ID，用于记忆管理
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
            session_id: 会话ID，用于记忆管理
            **kwargs: 额外参数
            
        Returns:
            包含输出和中间步骤的结果字典
        """
        # ainvoke 方法与 invoke 方法功能相同，为了保持 LangChain 接口兼容性
        return await self.invoke(query, session_id, **kwargs)
    
    async def _emit_thinking_event(self, message: str):
        """发送思考事件"""
        if self._progress_callback:
            self._progress_callback({"type": "thinking", "message": message})
    
    def get_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        info = {
            "provider": "zhipu",
            "model": self.model,
            "temperature": self.temperature,
            "max_iterations": self.max_iterations,
            "initialized": self.is_initialized,
            "tool_count": len(self.tools),
            "tools": [tool.name for tool in self.tools] if self.tools else [],
            "memory_enabled": self.enable_memory
        }
        
        # GLM-4.5特殊能力信息
        if self.model == "glm-4.5":
            info.update({
                "model_type": "GLM-4.5 MoE",
                "context_window": "128K tokens",
                "max_output": "96K tokens", 
                "thinking_mode": True,
                "special_features": [
                    "深度思考模式",
                    "128K长上下文",
                    "代码生成专精",
                    "工具调用优化",
                    "复杂推理增强"
                ],
                "architecture": "混合专家模型(MoE)"
            })
        
        # 添加记忆信息
        if self.enable_memory and self.chat_memory:
            info["memory_info"] = self.chat_memory.get_memory_stats()
        
        return info
    
    def get_llm(self):
        """获取底层LLM实例用于流式输出"""
        return self.llm
    
    def get_llm_info(self) -> Dict[str, Any]:
        """获取LLM详细信息，包括思考模式状态"""
        llm_info = {
            "model": self.model,
            "temperature": self.temperature,
            "thinking_mode": False,  # 默认值
            "model_features": []
        }
        
        # GLM-4.5特殊信息
        if self.model == "glm-4.5":
            llm_info.update({
                "thinking_mode": True,  # GLM-4.5默认启用思考模式
                "context_window": "128K tokens",
                "max_output": "96K tokens",
                "architecture": "混合专家模型(MoE)",
                "model_features": [
                    "深度思考模式",
                    "128K长上下文", 
                    "代码生成专精",
                    "工具调用优化"
                ]
            })
        elif self.model == "glm-4-plus":
            llm_info.update({
                "context_window": "32K tokens",
                "max_output": "8K tokens", 
                "architecture": "Transformer",
                "model_features": [
                    "通用对话",
                    "推理分析",
                    "工具调用"
                ]
            })
        
        return llm_info
    
    def list_tools(self) -> List[str]:
        """列出工具名称"""
        return [tool.name for tool in self.tools]
    
    # 记忆管理方法
    def get_memory_stats(self) -> Optional[Dict[str, Any]]:
        """获取记忆统计信息"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.get_memory_stats()
        return None
    
    def clear_memory(self, session_id: str = "default") -> bool:
        """清空指定会话记忆"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.clear_session(session_id)
        return False
    
    def save_memory(self, session_id: str = "default") -> bool:
        """手动保存记忆"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.save_session(session_id)
        return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.list_sessions()
        return []
    
    def delete_session(self, session_id: str) -> bool:
        """删除指定会话"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.delete_session(session_id)
        return False
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详细信息"""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.get_session_info(session_id)
        return None
    
    def restore_session(self, session_id: str) -> bool:
        """恢复指定会话的记忆"""
        if self.enable_memory and self.chat_memory:
            # 检查会话是否存在
            if session_id in [s["session_id"] for s in self.chat_memory.list_sessions()]:
                logger.info(f"恢复会话记忆: {session_id}")
                return True
            else:
                logger.warning(f"会话不存在: {session_id}")
                return False
        return False


# 兼容性函数，保持向后兼容
async def build_zhipu_agent(
    model: str = "glm-4-plus",
    verbose: bool = False,
    temperature: float = 0.1,
    **kwargs
) -> ZhipuAgent:
    """
    创建并初始化智谱AI Agent
    
    Args:
        model: 智谱AI模型名称
        verbose: 是否显示详细日志
        temperature: 模型温度参数
        **kwargs: 其他参数
        
    Returns:
        初始化完成的ZhipuAgent实例
    """
    agent = ZhipuAgent(
        model=model,
        temperature=temperature,
        verbose=verbose,
        **kwargs
    )
    
    await agent.initialize()
    return agent


def build_simple_zhipu_chat(model: str = "glm-4-plus", **kwargs):
    """
    创建简单的智谱AI聊天模型（不包含工具）
    
    Args:
        model: 模型名称
        **kwargs: 其他参数
        
    Returns:
        智谱AI聊天模型实例
    """
    return create_zhipu_llm(model=model, **kwargs)


async def test_zhipu_agent():
    """测试智谱AI Agent"""
    print("🧪 测试智谱AI Agent...")
    
    try:
        # 创建Agent
        print("1. 创建Agent...")
        agent = await build_zhipu_agent(verbose=False)
        
        # 显示Agent信息
        info = agent.get_info()
        print(f"✅ Agent创建成功")
        print(f"   - 模型: {info['model']}")
        print(f"   - 工具数量: {info['tool_count']}")
        print(f"   - 工具列表: {', '.join(info['tools'])}")
        
        # 测试数学计算
        print("\n2. 测试数学计算:")
        result = agent.invoke("计算 25 + 37")
        print(f"   查询: 计算 25 + 37")
        print(f"   结果: {result['output']}")
        print(f"   工具调用次数: {result['tool_calls']}")
        
        # 测试搜索功能
        print("\n3. 测试搜索功能:")
        result = agent.invoke("搜索Python教程")
        print(f"   查询: 搜索Python教程")
        print(f"   结果: {result['output'][:200]}...")
        print(f"   工具调用次数: {result['tool_calls']}")
        
        print("\n✅ 所有测试完成!")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_zhipu_agent())