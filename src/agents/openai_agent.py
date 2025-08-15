"""
OpenAI Agent Implementation

基于OpenAI GPT模型的智能Agent实现
支持完整的工具集成和记忆功能
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.language_models import BaseChatModel

from ..llm.openai_llm import build_openai_chat, OpenAILLM
from ..memory.global_memory import GlobalMemoryManager
from ..tools.math_tools import add_numbers, calculate_math
from ..tools.search_tools import SEARCH_TOOLS
from ..tools.tavily_search_tool import get_available_tavily_tools
from ..tools.amap_search import get_available_amap_tools
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
    
    async def _create_agent(self):
        """创建Agent和AgentExecutor"""
        
        # 创建简化的中文优化提示词模板（避免编码问题）
        system_prompt = """你是一个专业的智能AI助手，采用ReAct（推理-行动）框架进行逻辑推理和问题解决。你具备多领域专业知识，能够通过系统化的思考过程和工具使用为用户提供准确、全面的帮助。

## 工作原则
你能够使用各种专业工具来回答用户问题。当需要获取信息、进行计算或执行特定任务时，你会自动选择和调用合适的工具。

### 思维过程标准
1. **问题解构**: 将复杂问题分解为可管理的子问题
2. **上下文整合**: 充分利用聊天历史中的相关信息
3. **策略规划**: 预先思考工具使用序列和可能的替代方案
4. **结果验证**: 评估工具输出的合理性和完整性
5. **用户导向**: 确保最终答案直接回应用户的核心需求

### 工具使用规范
- **精确选择**: 根据问题类型选择最合适的工具
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

当前时间：{current_time}
"""
        
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
        
        self._agent_executor = AgentExecutor(
            agent=self._agent,
            tools=self._tools,
            verbose=verbose_setting,
            handle_parsing_errors=True,
            max_iterations=10,
            max_execution_time=300,  # 5分钟超时
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
            
            # 统计工具调用次数
            tool_calls = 0
            if "intermediate_steps" in result:
                tool_calls = len(result["intermediate_steps"])
            
            return {
                "success": True,
                "output": result.get("output", ""),
                "tool_calls": tool_calls,
                "session_id": session_id
            }
            
        except Exception as e:
            try:
                logger.error(f"Agent invoke failed: {str(e)}")
            except UnicodeEncodeError:
                logger.error(f"Agent调用失败: {str(e)}".encode('utf-8', errors='ignore').decode('utf-8'))
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "tool_calls": 0,
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
            
            # 统计工具调用次数
            tool_calls = 0
            if "intermediate_steps" in result:
                tool_calls = len(result["intermediate_steps"])
            
            return {
                "success": True,
                "output": result.get("output", ""),
                "tool_calls": tool_calls,
                "session_id": session_id
            }
            
        except Exception as e:
            try:
                logger.error(f"Agent async invoke failed: {str(e)}")
            except UnicodeEncodeError:
                logger.error(f"Agent异步调用失败: {str(e)}".encode('utf-8', errors='ignore').decode('utf-8'))
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "tool_calls": 0,
                "session_id": session_id
            }
    
    def get_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        llm_info = OpenAILLM(self.api_key, self.model).get_model_info()
        
        return {
            "provider": "openai",
            "model": self.model,
            "temperature": self.temperature,
            "initialized": self._initialized,
            "memory_enabled": self.enable_memory,
            "tool_count": len(self._tools),
            "tools": [tool.name for tool in self._tools] if self._tools else [],
            "llm_info": llm_info
        }
    
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