# LangChain 1.0.0 API 详细分析

## 1. create_agent 函数详解

### 函数签名

```python
from langchain.agents import create_agent

def create_agent(
    model: str | BaseChatModel,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | None = None,
    middleware: Sequence[AgentMiddleware[AgentState[ResponseT], ContextT]] = (),
    response_format: ResponseFormat[ResponseT] | type[ResponseT] | None = None,
    state_schema: type[AgentState[ResponseT]] | None = None,
    context_schema: type[ContextT] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None
) -> CompiledStateGraph[AgentState[ResponseT], ContextT, _InputAgentState, _OutputAgentState[ResponseT]]
```

### 参数说明

#### model (必需)
- 类型: `str | BaseChatModel`
- 说明: 语言模型，可以是字符串标识符或 ChatModel 实例
- 示例:
  ```python
  # 字符串形式 (使用 init_chat_model 自动初始化)
  model="openai:gpt-4"
  model="anthropic:claude-sonnet-4-5"
  
  # 实例形式 (我们项目使用这种方式)
  from langchain_openai import ChatOpenAI
  model=ChatOpenAI(model="gpt-4", temperature=0.7)
  ```

#### tools (可选)
- 类型: `Sequence[BaseTool | Callable | dict] | None`
- 说明: 工具列表，如果为 None 或空列表，agent 只包含模型节点，无工具调用循环
- 支持格式:
  ```python
  # 1. BaseTool 实例
  tools=[TavilySearchTool(), CalculatorTool()]
  
  # 2. 普通函数 (自动转换为工具)
  def get_weather(location: str) -> str:
      """Get weather for location."""
      return f"Weather in {location}"
  tools=[get_weather]
  
  # 3. 字典格式
  tools=[{
      "name": "search",
      "description": "Search the web",
      "parameters": {...}
  }]
  ```

#### system_prompt (可选)
- 类型: `str | None`
- 说明: 系统提示词，会转换为 SystemMessage 并添加到消息列表开头
- 特点: 
  - 简化的提示词格式，不再需要复杂的 PromptTemplate
  - 自动处理变量插值
- 示例:
  ```python
  system_prompt="""You are a helpful assistant. 
  Use the provided tools to answer questions.
  Always be concise and accurate."""
  ```

#### middleware (可选)
- 类型: `Sequence[AgentMiddleware]`
- 说明: 中间件序列，用于拦截和修改 agent 行为
- 用途:
  - 日志记录
  - 权限检查
  - 请求/响应修改
  - 自定义控制流

#### checkpointer (可选)
- 类型: `Checkpointer | None`
- 说明: Checkpoint 保存器，用于持久化状态（替代旧版的 RunnableWithMessageHistory）
- 用途:
  - 保存对话历史
  - 支持多轮对话
  - 状态恢复
- 示例:
  ```python
  from langgraph.checkpoint.memory import MemorySaver
  
  checkpointer = MemorySaver()
  graph = create_agent(model=llm, tools=tools, checkpointer=checkpointer)
  
  # 使用时指定 thread_id
  result = await graph.ainvoke(
      {"messages": [...]},
      config={"configurable": {"thread_id": "session_123"}}
  )
  ```

#### debug (可选)
- 类型: `bool`
- 说明: 是否启用详细日志（替代旧版的 verbose）
- 默认: `False`

#### name (可选)
- 类型: `str | None`
- 说明: Graph 名称，在构建多 agent 系统时特别有用

### 返回值

返回 `CompiledStateGraph` 实例，这是一个可运行的状态图。

## 2. CompiledStateGraph 接口分析

### 核心方法

#### ainvoke()

```python
async def ainvoke(
    self,
    input: dict,  # 输入状态
    config: RunnableConfig | None = None,  # 运行配置
    *,
    context: ContextT | None = None,  # 上下文
    stream_mode: StreamMode = 'values',  # 流模式
    output_keys: str | Sequence[str] | None = None,  # 输出键
    interrupt_before: All | Sequence[str] | None = None,  # 中断点
    interrupt_after: All | Sequence[str] | None = None,
    **kwargs
) -> dict[str, Any]
```

**参数说明:**

- `input`: 输入状态，对于 agent 是 `{"messages": [...]}`
- `config`: 运行配置，包括:
  ```python
  config = {
      "configurable": {
          "thread_id": "session_123",  # 用于 checkpointer
          # 其他配置项
      },
      "timeout": 30,  # 超时时间
      "max_concurrency": 10,  # 最大并发
  }
  ```
- `stream_mode`: 流模式
  - `'values'`: 返回完整状态
  - `'updates'`: 只返回更新
  - `'messages'`: 只返回消息
- `output_keys`: 指定返回哪些状态键
- `interrupt_before/after`: 在特定节点前后中断执行

**返回值:**

```python
{
    "messages": [
        HumanMessage(content="user query"),
        AIMessage(content="thinking...", tool_calls=[...]),
        ToolMessage(content="tool result", tool_call_id="..."),
        AIMessage(content="final answer")
    ]
}
```

#### astream()

```python
async def astream(
    self,
    input: dict,
    config: RunnableConfig | None = None,
    *,
    stream_mode: StreamMode | Sequence[StreamMode] | None = None,
    **kwargs
) -> AsyncIterator[dict[str, Any]]
```

用于流式返回结果，每次迭代返回一个状态更新。

**使用示例:**

```python
async for chunk in graph.astream({"messages": [HumanMessage(content="Hello")]}):
    print(chunk)
    # 输出格式取决于 stream_mode
```

## 3. AgentState 结构

### TypedDict 定义

```python
from typing_extensions import TypedDict, Required, NotRequired

class AgentState(TypedDict):
    """Agent 的状态结构"""
    
    # 必需字段
    messages: Required[List[AnyMessage]]
    
    # 可选字段
    jump_to: NotRequired[Optional[Literal['tools', 'model', 'end']]]
    structured_response: NotRequired[ResponseT]
```

### 字段说明

#### messages (必需)
- 类型: `List[AnyMessage]`
- 说明: 消息列表，包含对话历史和工具调用
- 支持的消息类型:
  - `HumanMessage`: 用户输入
  - `AIMessage`: AI 响应
  - `SystemMessage`: 系统提示
  - `ToolMessage`: 工具执行结果
  - `FunctionMessage`: 函数调用结果
  - 各种 Chunk 类型（用于流式输出）

#### jump_to (可选)
- 类型: `Optional[Literal['tools', 'model', 'end']]`
- 说明: 控制执行流，指定下一步跳转到哪个节点
- 用途: 自定义控制流逻辑

#### structured_response (可选)
- 类型: `ResponseT` (泛型)
- 说明: 结构化响应，用于返回 Pydantic 模型等结构化数据

### 自定义 State Schema

可以扩展 `AgentState` 添加自定义字段：

```python
from typing_extensions import TypedDict

class CustomAgentState(AgentState):
    """自定义 Agent 状态"""
    user_id: str
    session_metadata: dict
    custom_context: str

# 使用自定义 state
graph = create_agent(
    model=llm,
    tools=tools,
    state_schema=CustomAgentState
)
```

## 4. Message 类型详解

### AIMessage

```python
from langchain_core.messages import AIMessage

AIMessage(
    content: str | List[Union[str, dict]],  # 消息内容
    tool_calls: List[ToolCall] = [],  # 工具调用列表
    id: str | None = None,  # 消息 ID
    additional_kwargs: dict = {},  # 额外参数
    response_metadata: dict = {},  # 响应元数据
)
```

**tool_calls 结构:**

```python
[
    {
        "name": "tool_name",  # 工具名称
        "args": {"param": "value"},  # 工具参数
        "id": "call_xxxxx",  # 调用 ID
        "type": "tool_call"  # 类型
    }
]
```

### ToolMessage

```python
from langchain_core.messages import ToolMessage

ToolMessage(
    content: str,  # 工具返回的内容
    tool_call_id: str,  # 对应的 tool_call ID
    name: str | None = None,  # 工具名称
)
```

### HumanMessage

```python
from langchain_core.messages import HumanMessage

HumanMessage(
    content: str | List[Union[str, dict]],  # 用户输入
    id: str | None = None,
    name: str | None = None,
)
```

## 5. Config 配置详解

### RunnableConfig 结构

```python
config = {
    # Checkpointer 相关配置
    "configurable": {
        "thread_id": "session_123",  # 会话 ID
        "checkpoint_id": "xxx",  # Checkpoint ID
        "checkpoint_ns": "namespace",  # Checkpoint 命名空间
    },
    
    # 执行配置
    "timeout": 30,  # 超时时间（秒）
    "max_concurrency": 10,  # 最大并发数
    "recursion_limit": 25,  # 递归限制
    
    # Callbacks
    "callbacks": [callback_handler],  # 回调处理器列表
    
    # 标签和元数据
    "tags": ["production", "user_123"],  # 标签
    "metadata": {"user": "xxx", "session": "yyy"},  # 元数据
    
    # 运行时配置
    "run_name": "agent_run_001",  # 运行名称
    "run_id": "unique_run_id",  # 运行 ID
}
```

### thread_id 的使用

`thread_id` 用于标识不同的对话线程，配合 checkpointer 使用：

```python
# 第一次调用
result1 = await graph.ainvoke(
    {"messages": [HumanMessage(content="Hello")]},
    config={"configurable": {"thread_id": "user_123"}}
)

# 第二次调用，使用相同的 thread_id，会自动加载历史
result2 = await graph.ainvoke(
    {"messages": [HumanMessage(content="What did I say?")]},
    config={"configurable": {"thread_id": "user_123"}}
)
# AI 可以访问之前的对话历史
```

## 6. 工具调用流程

### 执行流程

1. **用户输入** → `{"messages": [HumanMessage(...)]}`

2. **Agent 节点** → LLM 处理，返回 `AIMessage`
   - 如果需要工具: `AIMessage(content="...", tool_calls=[...])`
   - 如果不需要工具: `AIMessage(content="final answer")`

3. **Tools 节点** (如果有 tool_calls)
   - 执行工具
   - 返回 `ToolMessage(content="result", tool_call_id="...")`

4. **返回 Agent 节点** → 再次调用 LLM，此时输入包含:
   - 原始 HumanMessage
   - 第一次的 AIMessage (with tool_calls)
   - ToolMessage (工具结果)

5. **重复 2-4** 直到 AIMessage 不包含 tool_calls

6. **结束** → 返回完整的 messages 列表

### 完整示例

```python
# 输入
input_state = {
    "messages": [HumanMessage(content="What's the weather in SF?")]
}

# 执行
result = await graph.ainvoke(input_state)

# 输出
result = {
    "messages": [
        HumanMessage(content="What's the weather in SF?"),
        AIMessage(
            content="Let me check the weather for you.",
            tool_calls=[{
                "name": "get_weather",
                "args": {"location": "San Francisco"},
                "id": "call_001"
            }]
        ),
        ToolMessage(
            content="Sunny, 72°F",
            tool_call_id="call_001",
            name="get_weather"
        ),
        AIMessage(
            content="The weather in San Francisco is sunny with a temperature of 72°F."
        )
    ]
}
```

## 7. 与旧版 API 的映射

### 输入格式映射

| 旧版 | 新版 | 转换 |
|------|------|------|
| `{"input": "query"}` | `{"messages": [HumanMessage(content="query")]}` | 包装为 HumanMessage |

### 输出格式映射

| 旧版字段 | 新版提取方式 |
|---------|-------------|
| `output` | 最后一个 AIMessage 的 content |
| `intermediate_steps` | 从 AIMessage.tool_calls 和 ToolMessage 重构 |

### 配置参数映射

| 旧版 AgentExecutor 参数 | 新版方案 |
|------------------------|---------|
| `max_iterations` | 通过 config 的 recursion_limit 或自定义 middleware |
| `max_execution_time` | config 的 timeout |
| `verbose` | debug=True |
| `handle_parsing_errors` | 内置处理 |
| `return_intermediate_steps` | 始终在 messages 中 |

## 8. 使用示例

### 简单场景

```python
graph = create_agent(
    model=llm,
    tools=tools,
    system_prompt="You are a helpful assistant."
)

result = await graph.ainvoke({
    "messages": [HumanMessage(content="user query")]
})
```

### 带历史记录

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = create_agent(
    model=llm,
    tools=tools,
    checkpointer=checkpointer
)

result = await graph.ainvoke(
    {"messages": [HumanMessage(content="Hello")]},
    config={"configurable": {"thread_id": "session_123"}}
)
```

## 下一步

请参考 [架构设计方案](./architecture_design.md) 了解如何在项目中应用这些 API。

