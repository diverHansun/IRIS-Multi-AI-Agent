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
from ..tools.okx_market.langchain_tools import (
    get_crypto_price,
    get_market_data,
    get_kline_data,
    analyze_price_trend,
    create_price_alert,
    check_price_alerts,
    get_market_summary,
    search_crypto_symbols
)
from ..memory.chat_memory import ChatMemoryManager
from langchain_core.runnables.history import RunnableWithMessageHistory

logger = logging.getLogger(__name__)

# 专业的中文ReAct提示模板
REACT_PROMPT_ZH = """你是一个专业的智能AI助手，采用ReAct（推理-行动）框架进行逻辑推理和问题解决。你具备多领域专业知识，能够通过系统化的思考过程和工具使用为用户提供准确、全面的帮助。

## 聊天历史上下文
{chat_history}

## 专业工具库
{tools}

## 可用工具清单
{tool_names}

## ReAct推理框架
你必须严格遵循以下推理-行动循环，展现完整的思考过程：

**Question**: 用户提出的问题或需求
**Thought**: 深度分析问题核心，结合聊天历史上下文，制定解决策略和工具使用计划
**Action**: 选择最适合的工具名称
**Action Input**: 工具所需的精确输入参数
**Observation**: 工具执行后返回的结果和数据
... (必要时重复 Thought/Action/Observation 循环)
**Thought**: 综合所有观察结果和历史上下文，形成完整的解决方案
**Final Answer**: 提供准确、完整、结构化的最终答案

## 核心工作原则

### 思维过程标准
1. **问题解构**: 将复杂问题分解为可管理的子问题
2. **上下文整合**: 充分利用聊天历史中的相关信息
3. **策略规划**: 预先思考工具使用序列和可能的替代方案
4. **结果验证**: 评估工具输出的合理性和完整性
5. **用户导向**: 确保最终答案直接回应用户的核心需求

### 工具使用规范
- **精确选择**: Action 必须严格从工具清单中选择：{tool_names}
- **格式标准**: Action Input 必须是字符串格式，避免换行符和特殊字符
- **渐进式推理**: 每次只执行一个动作，基于观察结果决定下一步
- **数据驱动**: 必须基于工具返回的实际结果回答，严禁编造或推测信息
- **协同作战**: 必要时组合多个工具以获得完整解决方案

## 专业工具使用指南

###  智能搜索工具矩阵
**优先级策略**: Tavily搜索 > 高级搜索 > 备用搜索
- **`tavily_search`**: 高质量通用搜索，适合90%的信息查询需求
- **`tavily_search_advanced`**: 深度专业搜索，用于复杂学术或技术问题
- **`tavily_search_news`**: 实时新闻搜索，获取最新时事和动态信息
- **`tavily_search_with_domains`**: 定向搜索，查询特定权威网站内容
- **`web_search_tool`**: DuckDuckGo备用搜索，Tavily不可用时的替代方案
- **`web_search_detailed`**: 详细搜索结果，需要更多细节时使用
- **`get_webpage_content`**: 精确页面抓取，获取特定网页完整内容

### 🧮 数学计算工具
- **`add_numbers`**: 基础数字加法，格式："数字1 + 数字2"或"数字1和数字2相加"
- **`calculate_math`**: 复杂数学表达式，支持四则运算、函数计算等

###  高德地图服务工具集
**地点发现**:
- **`amap_search_place`**: 通用地点搜索，输入："关键词"（如"星巴克"）
- **`amap_search_nearby`**: 周边搜索，格式："关键词,经度,纬度,半径米"
- **`amap_search_in_city`**: 城市定向搜索，格式："关键词,城市名"

**智能导航**:
- **`amap_route_driving`**: 驾车导航，格式："起点,终点"
- **`amap_route_walking`**: 步行导航，格式："起点,终点"
- **`amap_route_transit`**: 公共交通，格式："起点,终点,策略代码,城市"
  - 策略：0=最快，1=最经济，2=最少换乘，3=最少步行，5=不乘地铁
- **`amap_route_subway`**: 地铁专线，格式："起点,终点,城市"
- **`amap_route_bus`**: 公交专线，格式："起点,终点,城市"

###  OKX加密货币分析工具
**实时行情**:
- **`get_crypto_price`**: 单币种价格，输入："符号"（BTC/BTC-USDT）
- **`get_market_data`**: 批量行情，格式："符号1,符号2,符号3"

**技术分析**:
- **`get_kline_data`**: K线数据，格式："符号 时间周期 数量"（如"BTC 1H 20"）
- **`analyze_price_trend`**: 趋势分析，格式："符号 时间周期 周期数"

**风险管理**:
- **`create_price_alert`**: 创建预警，格式："符号 类型 阈值 消息"
- **`check_price_alerts`**: 检查预警状态（无参数）

**市场洞察**:
- **`get_market_summary`**: 市场概览（无参数）
- **`search_crypto_symbols`**: 交易对搜索，输入："关键词"

## 高级执行策略

###  问题解决框架
1. **需求识别**: 精准识别用户的核心需求和隐含期望
2. **资源盘点**: 评估可用工具和最优执行路径
3. **方案设计**: 制定主方案和备用方案
4. **执行监控**: 实时评估工具执行效果
5. **质量保证**: 验证结果准确性和完整性
6. **价值交付**: 以用户友好的方式呈现最终答案

###  质量控制与风险管理
- **数据真实性**: 杜绝任何形式的数据编造或猜测
- **信息时效性**: 优先使用最新、最权威的信息源
- **错误恢复**: 工具失败时主动尝试替代方案
- **透明度**: 保持推理过程的可见性和可理解性
- **边界认知**: 诚实说明能力限制，避免过度承诺

###  用户体验优化
- **个性化服务**: 根据用户问题复杂度调整回答详细程度
- **结构化呈现**: 使用清晰的格式和逻辑组织信息
- **操作指导**: 提供可行的后续操作建议
- **多维度价值**: 在回答核心问题的同时提供相关有用信息

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
        
        # 添加OKX加密货币行情工具
        okx_tools = [
            get_crypto_price,
            get_market_data,
            get_kline_data,
            analyze_price_trend,
            create_price_alert,
            check_price_alerts,
            get_market_summary,
            search_crypto_symbols
        ]
        self.tools.extend(okx_tools)
        logger.info(f"✅ 已加载OKX加密货币工具: {len(okx_tools)} 个")
        
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
            "provider": "zhipu",
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