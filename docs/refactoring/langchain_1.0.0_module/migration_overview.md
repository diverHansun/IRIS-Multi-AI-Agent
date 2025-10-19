# LangChain 1.0.0 Agent API 迁移概述

## 文档目的

本文档详细说明了将项目从旧版 LangChain Agent API 迁移到 LangChain 1.0.0 新版 API 的完整方案。

## 版本信息

- 当前版本: LangChain 1.0.0, LangChain-Core 1.0.0, LangChain-Community 0.4
- 迁移范围: Agent 创建和执行相关代码
- 影响模块: 
  - `src/agents/basicagents/adapters/`
  - `src/agents/basicagents/instances/base_agent.py`
  - `src/components/shared/memory/`

## 核心 API 变化

### 1. Agent 创建方式变化

#### 旧版 API (已废弃)

```python
from langchain.agents import (
    create_react_agent,
    create_tool_calling_agent,
    AgentExecutor
)
from langchain_core.prompts import PromptTemplate

# 创建 ReAct Agent
prompt = PromptTemplate.from_template(template_text)
agent = create_react_agent(llm, tools, prompt)

# 创建 Tool Calling Agent
prompt = ChatPromptTemplate.from_messages([...])
agent = create_tool_calling_agent(llm, tools, prompt)

# 创建 Executor
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=10,
    verbose=True,
    return_intermediate_steps=True
)

# 执行
result = await executor.ainvoke({"input": "user query"})
# 返回: {"output": "...", "intermediate_steps": [...]}
```

#### 新版 API (LangChain 1.0.0)

```python
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

# 统一的 Agent 创建方式
graph = create_agent(
    model=llm,  # 直接传入 LLM 实例
    tools=tools,
    system_prompt="System instructions...",  # 使用简单的 system_prompt
    # 可选参数
    checkpointer=checkpointer,  # 用于持久化状态
    interrupt_before=None,
    interrupt_after=None,
    debug=False,
)

# 执行 (输入输出格式完全不同)
result = await graph.ainvoke(
    {"messages": [HumanMessage(content="user query")]},
    config={"configurable": {"thread_id": "session_id"}}
)
# 返回: {"messages": [HumanMessage(...), AIMessage(...), ToolMessage(...), ...]}
```

### 2. 关键差异对比

| 方面 | 旧版 API | 新版 API |
|------|---------|----------|
| 导入路径 | `langchain.agents.create_react_agent` | `langchain.agents.create_agent` |
| Agent 类型 | 需要选择 ReAct/ToolCalling | 统一的 `create_agent` |
| Prompt 格式 | 复杂的 PromptTemplate | 简单的 system_prompt 字符串 |
| 返回类型 | `AgentExecutor` | `CompiledStateGraph` |
| 输入格式 | `{"input": str}` | `{"messages": [Message, ...]}` |
| 输出格式 | `{"output": str, "intermediate_steps": [...]}` | `{"messages": [Message, ...]}` |
| 工具调用信息 | 在 intermediate_steps 中 | 在 messages 中的 AIMessage.tool_calls |
| 配置方式 | 构造函数参数 (max_iterations, verbose) | 在 create_agent 中设置 |
| 状态管理 | 通过 RunnableWithMessageHistory | 原生支持 checkpointer |

### 3. AgentState 结构

新版 API 使用 `AgentState` TypedDict 作为状态结构：

```python
from langchain.agents.middleware.types import AgentState

# AgentState 结构
{
    "messages": Required[List[AnyMessage]],  # 必需，消息列表
    "jump_to": NotRequired[Optional[Literal['tools', 'model', 'end']]],  # 可选，控制流
    "structured_response": NotRequired[ResponseT]  # 可选，结构化响应
}
```

### 4. CompiledStateGraph 接口

```python
# ainvoke 签名
async def ainvoke(
    self,
    input: dict,
    config: RunnableConfig | None = None,
    *,
    context: ContextT | None = None,
    stream_mode: StreamMode = 'values',
    print_mode: StreamMode | Sequence[StreamMode] = (),
    output_keys: str | Sequence[str] | None = None,
    interrupt_before: All | Sequence[str] | None = None,
    interrupt_after: All | Sequence[str] | None = None,
    durability: Durability | None = None,
    **kwargs: Any
) -> dict[str, Any] | Any

# astream 签名
async def astream(
    self,
    input: dict,
    config: RunnableConfig | None = None,
    *,
    context: ContextT | None = None,
    stream_mode: StreamMode | Sequence[StreamMode] | None = None,
    # ... 其他参数
) -> AsyncIterator[dict[str, Any] | Any]
```

## 迁移策略

### 方案选择

我们选择**方案 B: 直接修改调用代码**，理由：

1. 更符合新版 API 设计理念
2. 避免引入额外的兼容层
3. 长期维护更简单
4. 充分利用新 API 的特性（如原生 checkpointer）

### 迁移范围

需要修改的模块：

1. **Agent Adapters** (`src/agents/basicagents/adapters/`)
   - `base.py` - 修改基类接口
   - `zhipu_agent_adapter.py`
   - `openai_agent_adapter.py`
   - `ollama_agent_adapter.py`

2. **Base Agent** (`src/agents/basicagents/instances/base_agent.py`)
   - 修改 `_build_agent_executor_with_adapter()` 
   - 修改 `_execute_query()` 方法
   - 修改 `_extract_tool_names()` 方法
   - 修改 `_build_agent_with_memory()` 方法

3. **Memory Management** (`src/components/shared/memory/`)
   - 评估是否需要更新 `RunnableWithMessageHistory` 的使用方式
   - 考虑使用新版的 `checkpointer` 机制

## 主要挑战

### 1. 输入输出格式转换

**挑战**: 旧代码期望 `{"input": str}` 输入和 `{"output": str, "intermediate_steps": [...]}` 输出

**解决方案**: 在 BaseAgent 中创建转换层

```python
# 输入转换
def _prepare_graph_input(self, query: str) -> dict:
    return {"messages": [HumanMessage(content=query)]}

# 输出转换
def _parse_graph_output(self, result: dict) -> dict:
    messages = result.get("messages", [])
    # 提取最后的 AI 消息作为输出
    # 提取工具调用作为 intermediate_steps
    return {
        "output": ...,
        "intermediate_steps": ...,
        "success": True,
        "tool_calls": ...,
        "tool_names": ...
    }
```

### 2. 工具调用信息提取

**挑战**: 旧版在 `intermediate_steps` 中存储 `(AgentAction, observation)` 元组，新版在 `AIMessage.tool_calls` 中

**解决方案**: 遍历 messages 列表，从 AIMessage 中提取 tool_calls

```python
def _extract_tool_calls_from_messages(self, messages: List[AnyMessage]) -> List[Tuple]:
    intermediate_steps = []
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls'):
            for tool_call in msg.tool_calls:
                # 构造类似旧格式的结构
                action = AgentAction(
                    tool=tool_call.get('name'),
                    tool_input=tool_call.get('args'),
                    log=f"Tool call: {tool_call.get('name')}"
                )
                # 查找对应的 ToolMessage
                observation = self._find_tool_response(messages, i+1, tool_call)
                intermediate_steps.append((action, observation))
    return intermediate_steps
```

### 3. Memory 集成

**挑战**: 旧版使用 `RunnableWithMessageHistory` 包装 `AgentExecutor`

**选项 A**: 继续使用 `RunnableWithMessageHistory` 包装 `CompiledStateGraph`
- 优点: 最小化修改
- 缺点: 可能不是最优方案

**选项 B**: 使用新版的 `checkpointer` 机制
- 优点: 原生支持，更高效
- 缺点: 需要重构 memory 管理代码

**建议**: 先使用选项 A 保持兼容，后续逐步迁移到选项 B

### 4. 参数映射

旧版 `AgentExecutor` 参数在新版中的对应：

| 旧版参数 | 新版方案 |
|---------|---------|
| `max_iterations` | 需要通过 middleware 或自定义逻辑实现 |
| `max_execution_time` | 通过 config timeout 或 middleware |
| `verbose` | 使用 `debug=True` 参数 |
| `handle_parsing_errors` | 内置处理 |
| `return_intermediate_steps` | 始终在 messages 中可用 |

## 实施步骤

迁移分为以下阶段：

1. **Adapter Layer**: 更新所有 Adapter 的 `create_agent_executor()` → `create_agent_graph()`
2. **BaseAgent**: 重构 BaseAgent 的执行逻辑，添加输入输出转换层
3. **Memory Integration**: 评估并更新 Memory 系统（使用 checkpointer 或兼容层）
4. **Testing**: 全面测试确保兼容性

## 兼容性考虑

### 向后兼容性

由于 API 变化较大，完全的向后兼容不可行。但我们可以：

1. 保持对外接口不变 (`BaseAgent.invoke()` 签名不变)
2. 内部实现替换为新 API
3. 确保输出格式与旧版一致

### 渐进式迁移

如果需要渐进式迁移：

1. 创建新的 Adapter 基类 `BaseAgentAdapterV2`
2. 并行实现新旧两套 Adapter
3. 通过配置选择使用哪个版本
4. 逐步切换并验证

## 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 输出格式解析错误 | 中 | 高 | 充分的单元测试 |
| Memory 功能失效 | 中 | 高 | 分阶段测试，保留回退方案 |
| 性能下降 | 低 | 中 | 性能基准测试 |
| 第三方集成问题 | 低 | 中 | 检查所有外部依赖 |

## 参考资源

- LangChain 1.0.0 官方文档: https://docs.langchain.com/oss/python/langchain/agents
- LangGraph 文档: https://langchain-ai.github.io/langgraph/
- Agent State 文档: https://docs.langchain.com/oss/python/langchain/agents#agent-state
- Migration Guide: https://docs.langchain.com/oss/python/langchain/migration

## 下一步

继续阅读：
- [API 详细分析](./api_analysis.md) - 深入了解新 API 的使用方式
- [架构设计方案](./architecture_design.md) - 查看具体的重构设计和代码示例

