"""
智谱AI代理模块

基于LangChain的ReAct Agent实现，集成MCP搜索和数学工具。
简化版本，移除复杂的多类型Agent系统。
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool

from ..llm.zhipu_llm import create_zhipu_llm
from ..tools.math_tools import add_numbers, calculate_math
from ..tools.search_tools import SEARCH_TOOLS
from ..tools.tavily_search_tool import get_available_tavily_tools
from ..tools.amap_search import get_available_amap_tools
from ..memory.chat_memory import ChatMemoryManager
from langchain_core.runnables.history import RunnableWithMessageHistory

logger = logging.getLogger(__name__)

# 带聊天历史的中文ReAct提示模板
REACT_PROMPT_ZH = """你是一个功能强大的AI助手，具备逻辑推理和工具使用能力，可以帮助用户解决各种问题。

## 聊天历史
{chat_history}

## 可用工具列表
{tools}

## 工具名称
{tool_names}

## 工作流程
请严格按照以下ReAct（推理-行动）格式进行思考和行动：

Question: 用户的问题
Thought: 我需要分析这个问题，结合聊天历史中的上下文信息，思考解决方案和所需工具
Action: 工具名称
Action Input: 工具的输入参数
Observation: 工具返回的结果
... (根据需要重复 Thought/Action/Observation 循环)
Thought: 基于所有观察结果和聊天历史上下文，我现在可以给出最终答案
Final Answer: 完整、准确的最终回答

## 重要规则
1. **工具选择**: Action 必须是以下工具之一：{tool_names}
2. **输入格式**: Action Input 必须是字符串格式，避免换行符和特殊字符
3. **逐步推理**: 每次只执行一个动作，基于观察结果决定下一步
4. **准确性**: 必须基于工具返回的实际结果回答，严禁编造信息
5. **完整性**: 如果一个工具无法完全解决问题，考虑使用其他工具补充

## 工具使用指南
- **搜索类工具**:
  - `tavily_search`: 通用搜索，适用于大多数信息查询
  - `tavily_search_advanced`: 深度搜索，适用于复杂或专业问题
  - `tavily_search_news`: 新闻搜索，适用于时事和最新信息
  - `tavily_search_with_domains`: 指定域名搜索，适用于特定网站查询
  - `web_search_tool`: DuckDuckGo搜索，备用搜索引擎
  - `web_search_detailed`: 详细搜索结果

- **内容获取工具**:
  - `get_webpage_content`: 获取特定网页的完整内容

- **计算工具**:
  - `add_numbers`: 数字加法运算
  - `calculate_math`: 复杂数学计算和表达式求解

- **高德地图工具**:
  - `amap_search_place`: 地点搜索，输入格式："关键词"，如"星巴克"
  - `amap_search_nearby`: 附近搜索，输入格式："关键词,经度,纬度,半径"，如"餐厅,116.397477,39.908692,1000"
  - `amap_search_in_city`: 城市内搜索，输入格式："关键词,城市"，如"购物中心,北京"
  - `amap_route_driving`: 驾车路线规划，输入格式："起点,终点"，如"上海世博展览馆,上海火车站"
  - `amap_route_walking`: 步行路线规划，输入格式："起点,终点"，如"天安门,故宫"
  - `amap_route_transit`: 公共交通路线规划，输入格式："起点,终点,策略,城市"，如"天安门,故宫,0,北京"（0-最快，1-最经济，2-最少换乘，3-最少步行，5-不乘地铁）
  - `amap_route_subway`: 地铁路线规划，输入格式："起点,终点,城市"，如"天安门,故宫,北京"
  - `amap_route_bus`: 公交路线规划，输入格式："起点,终点,城市"，如"天安门,故宫,北京"

## 处理策略
1. **问题分析**: 首先理解用户问题的核心需求
2. **工具规划**: 选择最适合的工具序列
3. **错误处理**: 如果工具返回错误，尝试调整输入或使用替代工具
4. **结果验证**: 确保答案的准确性和完整性
5. **用户体验**: 以清晰、结构化的方式呈现最终答案

## 注意事项
- 保持思考过程的透明度，让用户了解推理步骤
- 如果问题超出工具能力范围，诚实说明限制
- 对于敏感或争议性话题，保持客观中立
- 优先使用最新、最权威的信息源
- 如果需要多个工具配合，合理安排使用顺序

现在开始处理用户的问题：

Question: {input}
Thought: {agent_scratchpad}"""


class ZhipuAgent:
    """简化的智谱AI Agent"""
    
    def __init__(self, 
                 model: str = "glm-4-plus",
                 temperature: float = 0.1,
                 verbose: bool = False,
                 max_iterations: int = 10,
                 enable_memory: bool = True,
                 memory_config: Optional[Dict[str, Any]] = None):
        """
        初始化智谱AI Agent
        
        Args:
            model: 智谱AI模型名称
            temperature: 温度参数
            verbose: 是否显示详细日志
            max_iterations: 最大迭代次数
            enable_memory: 是否启用记忆功能
            memory_config: 记忆配置参数
        """
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.enable_memory = enable_memory
        
        # 组件
        self.llm = None
        self.tools = []
        self.agent_executor = None
        self.is_initialized = False
        
        # 记忆管理
        self.chat_memory = None
        self.agent_with_memory = None
        if enable_memory:
            self._init_memory(memory_config or {})
    
    def _init_memory(self, config: Dict[str, Any]) -> None:
        """初始化记忆管理器"""
        try:
            # 使用ChatMemoryManager
            self.chat_memory = ChatMemoryManager(
                storage_path=config.get("storage_path"),
                max_messages=config.get("max_messages", 20),
                max_tokens=config.get("max_tokens", 4000),
                auto_save=config.get("auto_save", True)
            )
            
            logger.info(f"聊天记忆管理器初始化完成")
        except Exception as e:
            logger.error(f"记忆管理器初始化失败: {e}")
            self.enable_memory = False
        
    async def initialize(self):
        """
        异步初始化Agent
        """
        try:
            logger.info("开始初始化智谱AI Agent...")
            
            # 1. 创建LLM
            self.llm = create_zhipu_llm(
                model=self.model,
                temperature=self.temperature,
                max_tokens=2048
            )
            logger.info(f"✅ LLM初始化完成: {self.model}")
            
            # 2. 收集工具
            self._collect_tools()
            
            # 3. 创建Agent
            self._build_agent()
            
            # 4. 创建带记忆的Agent（如果启用记忆）
            if self.enable_memory and self.chat_memory:
                self._build_agent_with_memory()
            
            self.is_initialized = True
            logger.info(f"✅ 智谱AI Agent初始化完成 - 模型: {self.model}, 工具数量: {len(self.tools)}")
            
        except Exception as e:
            logger.error(f"❌ Agent初始化失败: {e}")
            raise
    
    def _collect_tools(self):
        """收集所有可用工具"""
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
        
        logger.info(f"📋 总共收集到 {len(self.tools)} 个工具")
    
    def _build_agent(self):
        """构建Agent执行器"""
        try:
            # 创建提示模板
            prompt = PromptTemplate.from_template(REACT_PROMPT_ZH)
            
            # 创建ReAct Agent
            agent = create_react_agent(self.llm, self.tools, prompt)
            
            # 创建Agent执行器
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=self.verbose,
                handle_parsing_errors=True,
                max_iterations=self.max_iterations,
                early_stopping_method="force",
                return_intermediate_steps=True
            )
            
            logger.info("✅ Agent执行器创建完成")
            
        except Exception as e:
            logger.error(f"❌ Agent构建失败: {e}")
            raise
    
    def _build_agent_with_memory(self):
        """构建带记忆的Agent执行器"""
        try:
            if not self.agent_executor:
                raise ValueError("基础Agent必须先初始化")
            
            # 使用ChatMemoryManager创建带记忆的Runnable
            self.agent_with_memory = self.chat_memory.create_runnable_with_history(
                self.agent_executor
            )
            
            logger.info("✅ 带记忆的Agent执行器创建完成")
            
        except Exception as e:
            logger.error(f"❌ 带记忆的Agent构建失败: {e}")
            self.enable_memory = False
            raise
    
    def invoke(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """
        同步执行查询
        
        Args:
            query: 用户查询
            session_id: 会话ID，用于记忆管理
            
        Returns:
            包含输出和中间步骤的结果
        """
        if not self.is_initialized:
            return {
                "output": "Agent未初始化，请先调用 await agent.initialize()",
                "success": False,
                "error": "未初始化"
            }
        
        try:
            logger.info(f"处理查询: {query} (会话: {session_id})")
            
            # 使用带记忆的Agent（如果启用记忆）
            if self.enable_memory and self.agent_with_memory:
                # 使用RunnableWithMessageHistory标准接口
                result = self.agent_with_memory.invoke(
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
                result = self.agent_executor.invoke({"input": query})
                
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
            return {
                "output": f"抱歉，处理查询时出现错误: {str(e)}",
                "intermediate_steps": [],
                "success": False,
                "error": str(e)
            }
    
    async def ainvoke(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """
        异步执行查询
        
        Args:
            query: 用户查询
            
        Returns:
            包含输出和中间步骤的结果
        """
        if not self.is_initialized:
            return {
                "output": "Agent未初始化，请先调用 await agent.initialize()",
                "success": False,
                "error": "未初始化"
            }
        
        try:
            logger.info(f"异步处理查询: {query} (会话: {session_id})")
            
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
            logger.error(f"异步查询处理失败: {e}")
            return {
                "output": f"抱歉，异步处理查询时出现错误: {str(e)}",
                "intermediate_steps": [],
                "success": False,
                "error": str(e)
            }
    
    def get_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        info = {
            "model": self.model,
            "temperature": self.temperature,
            "max_iterations": self.max_iterations,
            "initialized": self.is_initialized,
            "tool_count": len(self.tools),
            "tools": [tool.name for tool in self.tools] if self.tools else [],
            "memory_enabled": self.enable_memory
        }
        
        # 添加记忆信息
        if self.enable_memory and self.chat_memory:
            info["memory_info"] = self.chat_memory.get_memory_stats()
        
        return info
    
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