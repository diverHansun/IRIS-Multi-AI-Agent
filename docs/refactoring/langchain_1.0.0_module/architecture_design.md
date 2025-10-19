# LangChain 1.0.0 迁移架构设计

## 1. 总体架构

### 1.1 当前架构

```
┌─────────────────────────────────────────────────────────┐
│                     Application Layer                    │
│            (CLI, Services, Commands)                     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    BaseAgent                             │
│  - _build_agent_executor_with_adapter()                  │
│  - _execute_query()                                      │
│  - _build_agent_with_memory()                            │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 AgentAdapter (Base)                      │
│  - get_agent_params()                                    │
│  - create_agent_executor() → AgentExecutor              │
└────────┬────────────────────────────────────────────────┘
         │
         ├─────────────┬─────────────┬───────────────┐
         ▼             ▼             ▼               ▼
┌──────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────┐
│ZhipuAdapter  │ │OpenAIAdapter│ │OllamaAdap│ │   ...    │
│              │ │             │ │ter       │ │          │
└──────────────┘ └─────────────┘ └──────────┘ └──────────┘

Data Flow (旧版):
  User Query → {"input": "query"}
              ↓
      AgentExecutor.ainvoke()
              ↓
  {"output": "...", "intermediate_steps": [...]}
```

### 1.2 目标架构

```
┌─────────────────────────────────────────────────────────┐
│                     Application Layer                    │
│            (CLI, Services, Commands)                     │
│                   [不变]                                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    BaseAgent                             │
│  - _build_graph_with_adapter()                          │
│  - _execute_query_with_graph()                          │
│  - _prepare_graph_input()                               │
│  - _parse_graph_output()                                │
│  - _build_graph_with_checkpointer()                     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 AgentAdapter (Base)                      │
│  - get_agent_params()                                    │
│  - create_agent_graph() → CompiledStateGraph            │
└────────┬────────────────────────────────────────────────┘
         │
         ├─────────────┬─────────────┬───────────────┐
         ▼             ▼             ▼               ▼
┌──────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────┐
│ZhipuAdapter  │ │OpenAIAdapter│ │OllamaAdap│ │   ...    │
│              │ │             │ │ter       │ │          │
└──────────────┘ └─────────────┘ └──────────┘ └──────────┘

Data Flow (新版):
  User Query → {"messages": [HumanMessage(content="query")]}
              ↓
      CompiledStateGraph.ainvoke()
              ↓
  {"messages": [HumanMessage(...), AIMessage(...), ...]}
              ↓
         解析提取
              ↓
  {"output": "...", "intermediate_steps": [...]}
```

## 2. 核心组件设计

### 2.1 BaseAgent 重构

```python
# src/agents/basicagents/instances/base_agent.py

class BaseAgent:
    """Base class for all agents (updated for LangChain 1.0.0)"""
    
    def __init__(self, ...):
        # 改名以反映新的类型
        self.agent_graph: Optional[CompiledStateGraph] = None  # 替代 agent_executor
        self.agent_graph_with_memory: Optional[Runnable] = None  # 替代 agent_with_memory
        self.checkpointer: Optional[Checkpointer] = None  # 新增
        # ... 其他属性保持不变
    
    # === 初始化方法 ===
    
    def _build_graph_with_adapter(self):
        """使用 Adapter 创建 CompiledStateGraph (替代 _build_agent_executor_with_adapter)"""
        try:
            if self.agent_adapter:
                self.agent_graph = self.agent_adapter.create_agent_graph(
                    llm=self.llm,
                    tools=self.tools,
                    checkpointer=self.checkpointer if self.enable_memory else None
                )
                logger.info("Agent graph created (using Agent Adapter)")
            else:
                logger.warning("No agent adapter provided")
        except Exception as e:
            logger.error(f"Agent graph creation failed: {e}", exc_info=True)
            raise
    
    def _build_graph_with_checkpointer(self):
        """
        使用 checkpointer 构建带记忆的 graph
        
        注意：
        - 方案 A: 如果 checkpointer 在 create_agent 时传入，则原生支持记忆
        - 方案 B: 如果需要兼容旧的 RunnableWithMessageHistory，在这里包装
        """
        try:
            if not self.agent_graph:
                raise ValueError("Base graph must be initialized first")
            
            if self.enable_memory:
                # 方案 A: checkpointer 已经在 create_agent 中设置
                # graph 本身已经支持记忆，无需额外包装
                if self.checkpointer:
                    logger.info("Agent graph with native checkpointer created")
                    self.agent_graph_with_memory = self.agent_graph
                
                # 方案 B: 兼容旧的 memory 系统（可选）
                elif self.global_memory_manager:
                    # 尝试使用 RunnableWithMessageHistory 包装
                    # 需要适配 messages 格式
                    self.agent_graph_with_memory = self._wrap_with_legacy_memory()
                    logger.info("Agent graph with legacy memory wrapper created")
                else:
                    logger.warning("Memory enabled but no checkpointer or memory manager")
            else:
                self.agent_graph_with_memory = self.agent_graph
                
        except Exception as e:
            logger.error(f"Graph with memory creation failed: {e}")
            self.enable_memory = False
            raise
    
    # === 输入输出转换方法 ===
    
    def _prepare_graph_input(self, query: str) -> Dict[str, Any]:
        """
        准备 graph 输入格式
        
        Args:
            query: 用户查询字符串
            
        Returns:
            符合 AgentState 格式的输入
        """
        from langchain_core.messages import HumanMessage
        
        return {
            "messages": [HumanMessage(content=query)]
        }
    
    def _parse_graph_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 graph 输出，转换为统一格式
        
        Args:
            result: graph.ainvoke() 的返回值
            
        Returns:
            标准化的结果格式
        """
        from langchain_core.messages import AIMessage, ToolMessage
        
        messages = result.get("messages", [])
        
        # 1. 提取最终输出 (最后一个 AIMessage 的 content)
        output = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                output = msg.content
                break
        
        # 2. 提取工具调用信息 (intermediate_steps)
        intermediate_steps = self._extract_intermediate_steps_from_messages(messages)
        
        # 3. 提取工具名称列表
        tool_names = self._extract_tool_names_from_steps(intermediate_steps)
        
        return {
            "output": output,
            "intermediate_steps": intermediate_steps,
            "success": True,
            "tool_calls": len(intermediate_steps),
            "tool_names": tool_names,
            "raw_messages": messages,  # 保留原始 messages 以便调试
        }
    
    def _extract_intermediate_steps_from_messages(
        self, 
        messages: List[Any]
    ) -> List[Tuple[AgentAction, str]]:
        """
        从 messages 列表中提取 intermediate_steps
        
        遍历 messages，找到包含 tool_calls 的 AIMessage，
        并匹配对应的 ToolMessage 作为观察结果。
        
        Args:
            messages: 消息列表
            
        Returns:
            (AgentAction, observation) 元组列表
        """
        from langchain_core.messages import AIMessage, ToolMessage
        from langchain_core.agents import AgentAction
        
        intermediate_steps = []
        
        # 构建 tool_call_id 到 ToolMessage 的映射
        tool_messages = {}
        for msg in messages:
            if isinstance(msg, ToolMessage):
                tool_messages[msg.tool_call_id] = msg
        
        # 遍历 AIMessage，提取 tool_calls
        for msg in messages:
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    # 创建 AgentAction
                    action = AgentAction(
                        tool=tool_call.get('name', ''),
                        tool_input=tool_call.get('args', {}),
                        log=f"Tool call: {tool_call.get('name', '')}"
                    )
                    
                    # 查找对应的 ToolMessage
                    tool_call_id = tool_call.get('id')
                    observation = ""
                    if tool_call_id and tool_call_id in tool_messages:
                        observation = tool_messages[tool_call_id].content
                    
                    intermediate_steps.append((action, observation))
        
        return intermediate_steps
    
    def _extract_tool_names_from_steps(
        self, 
        intermediate_steps: List[Tuple[AgentAction, str]]
    ) -> List[str]:
        """从 intermediate_steps 提取工具名称列表"""
        tool_names = []
        for action, _ in intermediate_steps:
            if hasattr(action, 'tool'):
                tool_names.append(action.tool)
        return tool_names
    
    # === 执行方法 ===
    
    async def _execute_query_with_graph(
        self,
        query: str,
        session_id: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        使用 graph 执行查询 (替代 _execute_query)
        
        Args:
            query: 用户查询
            session_id: 会话 ID
            **kwargs: 额外参数
            
        Returns:
            执行结果
        """
        try:
            # 准备输入
            graph_input = self._prepare_graph_input(query)
            
            # 准备配置
            config = self._prepare_graph_config(session_id, **kwargs)
            
            # 选择使用哪个 graph
            graph = self.agent_graph_with_memory if self.enable_memory else self.agent_graph
            
            if not graph:
                raise ValueError("Agent graph not initialized")
            
            # 执行
            raw_result = await graph.ainvoke(graph_input, config=config)
            
            # 解析输出
            result = self._parse_graph_output(raw_result)
            
            # 添加会话信息
            result.update({
                "session_id": session_id if self.enable_memory else None,
                "memory_enabled": self.enable_memory
            })
            
            # 保存会话 (如果使用旧的 memory 系统)
            if self.enable_memory and self.chat_memory:
                self.chat_memory.save_session(session_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}", exc_info=True)
            return {
                "output": f"Query execution failed: {str(e)}",
                "intermediate_steps": [],
                "success": False,
                "tool_calls": 0,
                "tool_names": [],
                "session_id": session_id,
                "memory_enabled": self.enable_memory
            }
    
    def _prepare_graph_config(
        self,
        session_id: str,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        准备 graph 执行的 config
        
        Args:
            session_id: 会话 ID
            timeout: 超时时间
            **kwargs: 其他配置
            
        Returns:
            RunnableConfig
        """
        config = {
            "configurable": {
                "thread_id": session_id,  # 用于 checkpointer
            }
        }
        
        # 添加超时
        if timeout:
            config["timeout"] = timeout
        
        # 添加其他配置
        if "recursion_limit" in kwargs:
            config["recursion_limit"] = kwargs["recursion_limit"]
        
        return config
    
    # === 公共接口 (保持不变) ===
    
    async def invoke(
        self,
        query: str,
        session_id: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        异步调用 agent (主接口)
        
        接口保持不变，内部实现更新为使用 graph
        """
        return await self._execute_query_with_graph(query, session_id, **kwargs)
```

### 2.2 AgentAdapter 重构

```python
# src/agents/basicagents/adapters/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

class AgentAdapter(ABC):
    """Base class for agent adapters (updated for LangChain 1.0.0)"""
    
    def __init__(
        self,
        provider: str,
        model: Optional[str],
        provider_registry: Optional[ProviderRegistry] = None,
    ):
        self.provider = provider
        self.model = model
        self.provider_registry = provider_registry or ProviderRegistry()
    
    def get_agent_params(self, **user_params) -> Dict[str, Any]:
        """
        获取 agent 参数
        
        从配置文件读取参数并与用户参数合并
        
        Returns:
            合并后的参数字典
        """
        # 从配置读取
        config = self.provider_registry.get_provider_config(self.provider)
        mode_defaults = config.get("agent", {}).get("mode_defaults", {})
        mode_overrides = config.get("agent", {}).get("mode_overrides", {}).get(self.model, {})
        
        # 合并参数
        params = {**mode_defaults, **mode_overrides, **user_params}
        
        return params
    
    @abstractmethod
    def create_agent_graph(
        self,
        llm,
        tools,
        checkpointer: Optional[Checkpointer] = None,
        **params
    ) -> CompiledStateGraph:
        """
        创建 CompiledStateGraph (替代 create_agent_executor)
        
        Args:
            llm: LLM 实例
            tools: 工具列表
            checkpointer: Checkpoint 保存器 (可选)
            **params: 额外参数
            
        Returns:
            CompiledStateGraph 实例
        """
        pass
    
    def supports_function_calling(self) -> bool:
        """判断模型是否支持 Function Calling"""
        return False
    
    def get_agent_type(self) -> str:
        """获取推荐的 Agent 类型"""
        return "react"
```

### 2.3 具体 Adapter 实现

```python
# src/agents/basicagents/adapters/zhipu_agent_adapter.py

from langchain.agents import create_agent
from .base import AgentAdapter

class ZhipuAgentAdapter(AgentAdapter):
    """Zhipu AI agent adapter (updated for LangChain 1.0.0)"""
    
    def __init__(self, model: Optional[str], provider_registry: Optional[ProviderRegistry] = None):
        super().__init__("ZHIPU", model, provider_registry=provider_registry)
    
    def create_agent_graph(
        self,
        llm,
        tools,
        checkpointer: Optional[Checkpointer] = None,
        **params
    ) -> CompiledStateGraph:
        """创建智谱 AI 的 Agent Graph"""
        
        # 获取参数
        agent_params = self.get_agent_params(**params)
        
        # 构建 system_prompt
        system_prompt = self._get_system_prompt()
        
        # 使用新的 create_agent API
        graph = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=checkpointer,
            debug=agent_params.get("verbose", False),
        )
        
        logger.info(
            f"Agent graph created for {self.model}: "
            f"debug={agent_params.get('verbose')}"
        )
        
        return graph
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        if self.model in ["glm-4.5", "glm-4.5-flash"]:
            # Tool Calling 模式的提示词
            return """你是一个有用的AI助手。你可以使用各种工具来帮助回答问题。
当需要使用工具时，请直接调用相应的工具函数。
工具会返回结果，然后你可以根据结果给出最终答案。"""
        else:
            # ReAct 模式的提示词
            return """你是一个有用的AI助手。你有权访问各种工具。
请按照以下步骤思考和行动：
1. 分析问题
2. 如果需要工具，选择合适的工具并调用
3. 根据工具结果继续思考
4. 当有足够信息时，给出最终答案"""
    
    def supports_function_calling(self) -> bool:
        """判断模型是否支持 Function Calling"""
        return self.model in ["glm-4.5", "glm-4.5-flash"]
```

## 3. Memory 集成方案

### 3.1 方案 A: 使用原生 Checkpointer (推荐)

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

class BaseAgent:
    def __init__(self, ...):
        # 初始化 checkpointer
        if self.enable_memory:
            # 选项 1: 内存 checkpointer (临时)
            self.checkpointer = MemorySaver()
            
            # 选项 2: SQLite checkpointer (持久化)
            # self.checkpointer = SqliteSaver("path/to/db.sqlite")
        else:
            self.checkpointer = None
```

优点:
- 原生支持，性能更好
- 代码更简洁
- 与 LangGraph 深度集成

缺点:
- 需要重构现有的 GlobalMemoryManager
- 数据格式变化（从旧格式迁移到新格式）

### 3.2 方案 B: 兼容旧的 RunnableWithMessageHistory

```python
from langchain_core.runnables.history import RunnableWithMessageHistory

class BaseAgent:
    def _wrap_with_legacy_memory(self) -> Runnable:
        """使用旧的 memory 系统包装 graph"""
        
        # 需要创建一个适配器，将 messages 格式转换为旧的 input/output 格式
        class GraphToLegacyAdapter(Runnable):
            def __init__(self, graph):
                self.graph = graph
            
            async def ainvoke(self, inputs, config=None):
                # 转换输入: {"input": "..."} → {"messages": [...]}
                if "input" in inputs:
                    graph_input = {
                        "messages": [HumanMessage(content=inputs["input"])]
                    }
                else:
                    graph_input = inputs
                
                # 调用 graph
                result = await self.graph.ainvoke(graph_input, config=config)
                
                # 转换输出: {"messages": [...]} → {"output": "..."}
                output = ""
                for msg in reversed(result.get("messages", [])):
                    if isinstance(msg, AIMessage):
                        output = msg.content
                        break
                
                return {"output": output, "intermediate_steps": []}
        
        adapter = GraphToLegacyAdapter(self.agent_graph)
        
        return RunnableWithMessageHistory(
            adapter,
            self.global_memory_manager.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history"
        )
```

优点:
- 兼容现有代码
- 渐进式迁移

缺点:
- 增加复杂性
- 性能开销
- 不是长期方案

### 3.3 推荐方案

1. **短期**: 使用方案 A (原生 Checkpointer) + 保留旧 memory 系统的读取能力
2. **中期**: 提供数据迁移工具，将旧格式转换为新格式
3. **长期**: 完全迁移到新的 checkpointer 系统

## 4. 配置参数处理

### 4.1 max_iterations 处理

新版 API 没有直接的 `max_iterations` 参数。有两种方案：

#### 方案 1: 使用 recursion_limit

```python
config = {
    "recursion_limit": agent_params.get("max_iterations", 25)
}

result = await graph.ainvoke(input, config=config)
```

#### 方案 2: 使用 Middleware

```python
from langchain.agents.middleware import AgentMiddleware

class MaxIterationsMiddleware(AgentMiddleware):
    def __init__(self, max_iterations: int):
        self.max_iterations = max_iterations
        self.current_iterations = 0
    
    async def on_tool_call(self, request, next):
        self.current_iterations += 1
        if self.current_iterations > self.max_iterations:
            raise StopIteration(f"Max iterations ({self.max_iterations}) reached")
        return await next(request)

# 使用
graph = create_agent(
    model=llm,
    tools=tools,
    middleware=[MaxIterationsMiddleware(max_iterations=10)]
)
```

### 4.2 max_execution_time 处理

使用 config 的 timeout:

```python
config = {
    "timeout": agent_params.get("max_execution_time", 30)  # 秒
}

try:
    result = await graph.ainvoke(input, config=config)
except TimeoutError:
    logger.error("Execution timeout")
```

### 4.3 verbose/debug 处理

```python
graph = create_agent(
    model=llm,
    tools=tools,
    debug=agent_params.get("verbose", False)
)
```

## 5. 错误处理和回退

### 5.1 错误处理策略

```python
async def _execute_query_with_graph(self, query: str, session_id: str = "default", **kwargs):
    try:
        # 执行主逻辑
        result = await self.agent_graph.ainvoke(input, config=config)
        return self._parse_graph_output(result)
        
    except TimeoutError as e:
        logger.error(f"Execution timeout: {e}")
        return {
            "output": "请求超时，请稍后重试",
            "success": False,
            "error_type": "timeout"
        }
        
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return {
            "output": "输入格式错误",
            "success": False,
            "error_type": "invalid_input"
        }
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            "output": f"执行失败: {str(e)}",
            "success": False,
            "error_type": "unknown"
        }
```

### 5.2 降级策略

如果新 API 失败，可以临时回退到旧 API（迁移过渡期）:

```python
async def _execute_query_with_fallback(self, query: str, session_id: str = "default"):
    try:
        # 尝试使用新 API
        return await self._execute_query_with_graph(query, session_id)
    except Exception as e:
        logger.warning(f"New API failed, falling back to old API: {e}")
        # 回退到旧 API (需要保留旧代码)
        if hasattr(self, '_execute_query_legacy'):
            return await self._execute_query_legacy(query, session_id)
        raise
```

## 6. 测试策略

### 6.1 单元测试

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_prepare_graph_input():
    """测试输入准备"""
    agent = BaseAgent(...)
    result = agent._prepare_graph_input("test query")
    
    assert "messages" in result
    assert len(result["messages"]) == 1
    assert result["messages"][0].content == "test query"

@pytest.mark.asyncio
async def test_parse_graph_output():
    """测试输出解析"""
    agent = BaseAgent(...)
    
    mock_result = {
        "messages": [
            HumanMessage(content="query"),
            AIMessage(content="response")
        ]
    }
    
    result = agent._parse_graph_output(mock_result)
    
    assert result["output"] == "response"
    assert result["success"] is True
```

### 6.2 集成测试

```python
@pytest.mark.asyncio
async def test_agent_execution_flow():
    """测试完整执行流程"""
    agent = ZhipuAgent(...)
    
    result = await agent.invoke("What is 2+2?")
    
    assert result["success"] is True
    assert "output" in result
    assert isinstance(result["tool_names"], list)
```

### 6.3 兼容性测试

```python
@pytest.mark.asyncio
async def test_output_format_compatibility():
    """测试输出格式与旧版兼容"""
    agent = BaseAgent(...)
    result = await agent.invoke("test")
    
    # 确保包含所有旧版字段
    required_fields = ["output", "intermediate_steps", "success", "tool_calls", "tool_names"]
    for field in required_fields:
        assert field in result
```

## 7. 迁移路径

### 步骤 1: 准备工作
- 备份当前代码
- 确保现有测试通过
- 创建迁移分支

### 步骤 2: 更新 Adapter 层
- 修改 `BaseAdapter.create_agent_executor()` → `create_agent_graph()`
- 更新 `ZhipuAgentAdapter`
- 更新 `OpenAIAgentAdapter`
- 更新 `OllamaAgentAdapter`
- 删除 `AgentExecutorWrapper` 临时代码

### 步骤 3: 重构 BaseAgent
- 重命名 `agent_executor` → `agent_graph`
- 实现 `_prepare_graph_input()`
- 实现 `_parse_graph_output()`
- 实现 `_extract_intermediate_steps_from_messages()`
- 更新 `_execute_query()` → `_execute_query_with_graph()`
- 更新 `_build_agent_with_memory()` → `_build_graph_with_checkpointer()`

### 步骤 4: Memory 集成
- 评估使用原生 checkpointer 还是保持兼容层
- 如果使用 checkpointer: 更新初始化和配置逻辑
- 如果保持兼容: 实现 `_wrap_with_legacy_memory()`

### 步骤 5: 测试验证
- 单元测试: 输入输出转换
- 集成测试: 完整流程
- 兼容性测试: 确保输出格式一致
- 性能测试: 对比新旧 API 性能

### 步骤 6: 清理
- 删除旧的 API 调用代码
- 更新文档和注释
- 代码审查

## 8. 迁移检查清单

**代码改动**
- [ ] `src/agents/basicagents/adapters/base.py`
- [ ] `src/agents/basicagents/adapters/zhipu_agent_adapter.py`
- [ ] `src/agents/basicagents/adapters/openai_agent_adapter.py`
- [ ] `src/agents/basicagents/adapters/ollama_agent_adapter.py`
- [ ] `src/agents/basicagents/instances/base_agent.py`
- [ ] `src/components/shared/memory/` (可选)

**测试覆盖**
- [ ] Adapter 创建测试
- [ ] 输入输出转换测试
- [ ] 工具调用提取测试
- [ ] Memory 功能测试
- [ ] 完整流程测试

