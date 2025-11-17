# 虚拟文件系统多Agent共享机制深度分析

## 执行摘要

**核心发现**: 虚拟文件系统在设计上**确实支持**main agent和subagents之间共享,但这是通过**状态拷贝+合并**机制实现的,而非真正的引用共享。

### 关键结论

| 维度 | 结论 |
|------|------|
| **是否支持多agent共享** | ✅ **支持** (通过状态拷贝+reducer合并) |
| **共享机制** | 状态拷贝到subagent → subagent执行 → 状态合并回main agent |
| **隔离级别** | messages和todos隔离,但`files`字典共享 |
| **设计模式** | Middleware模式 + Reducer模式 + 状态拷贝模式 |
| **是否为Singleton** | ❌ 不是单例,但工厂是隐式单例 |
| **持久化方式** | 内存(临时) 或 LangGraph Store(持久) |

---

## 一、核心架构解析

### 1.1 虚拟文件系统状态定义

**文件**: [src/components/deepagents/runtime_middlewares/virtual_filesystem/types.py](src/components/deepagents/runtime_middlewares/virtual_filesystem/types.py)

```python
def _file_data_reducer(
    current: Dict[str, FileData] | None,
    updates: Dict[str, FileData | None]
) -> Dict[str, FileData]:
    """合并文件系统更新,支持删除标记。

    这个reducer是实现多agent共享的核心机制!
    """
    if current is None:
        return {path: data for path, data in updates.items() if data is not None}

    merged: Dict[str, FileData] = dict(current)
    for path, data in updates.items():
        if data is None:
            merged.pop(path, None)  # None表示删除文件
        else:
            merged[path] = data      # 更新或创建文件
    return merged

class FilesystemState(AgentState):
    """LangGraph状态模式,用于虚拟文件系统。"""
    # 使用Annotated类型+reducer实现状态合并
    files: Annotated[NotRequired[Dict[str, FileData]], _file_data_reducer]
```

**关键点**:
- `_file_data_reducer`: 这是LangGraph的reducer函数,负责合并来自不同agent的文件系统更新
- `Annotated[..., _file_data_reducer]`: 告诉LangGraph在状态合并时调用这个reducer
- 支持增量更新:只传递变更的文件,不需要传递整个文件系统

### 1.2 状态排除机制

**文件**: [deepagents/libs/deepagents/deepagents/middleware/subagents.py:64](deepagents/libs/deepagents/deepagents/middleware/subagents.py#L64)

```python
# 传递给subagent时排除的状态键
_EXCLUDED_STATE_KEYS = ("messages", "todos")
```

**重要**: `files`键**不在**排除列表中,因此会被传递给subagent!

---

## 二、多Agent状态共享流程详解

### 2.1 完整数据流

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Agent Runtime                        │
│  State: {                                                    │
│    messages: [...],                                          │
│    todos: [...],                                             │
│    files: {                                                  │
│      "/workspace/shared/task.txt": FileData(...),           │
│      "/workspace/tool_results/search.json": FileData(...)   │
│    }                                                         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Main agent调用task工具
                              ▼
┌─────────────────────────────────────────────────────────────┐
│          _validate_and_prepare_state() 函数                  │
│  代码位置: subagents.py:324-330                               │
│                                                              │
│  # 拷贝状态,排除messages和todos                               │
│  subagent_state = {                                          │
│    k: v for k, v in runtime.state.items()                   │
│    if k not in _EXCLUDED_STATE_KEYS                         │
│  }                                                           │
│  # 结果:                                                      │
│  subagent_state = {                                          │
│    files: {  # ✅ files被拷贝了!                              │
│      "/workspace/shared/task.txt": FileData(...),           │
│      "/workspace/tool_results/search.json": FileData(...)   │
│    }                                                         │
│  }                                                           │
│  subagent_state["messages"] = [HumanMessage(...)]           │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 状态拷贝传递
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   SubAgent Runtime                           │
│  初始状态 = subagent_state (包含files拷贝)                     │
│                                                              │
│  SubAgent可以:                                               │
│  1. 读取 /workspace/shared/task.txt                         │
│  2. 写入 /workspace/shared/result.json                      │
│  3. 编辑现有文件                                              │
│                                                              │
│  执行后状态:                                                  │
│  {                                                           │
│    messages: [HumanMessage(...), AIMessage(...)],          │
│    files: {                                                  │
│      "/workspace/shared/task.txt": FileData(...),          │
│      "/workspace/tool_results/search.json": FileData(...), │
│      "/workspace/shared/result.json": FileData(...)  # 新   │
│    }                                                         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Subagent返回结果
                              ▼
┌─────────────────────────────────────────────────────────────┐
│       _return_command_with_state_update() 函数               │
│  代码位置: subagents.py:315-322                               │
│                                                              │
│  # 排除messages和todos,其他状态全部返回                       │
│  state_update = {                                            │
│    k: v for k, v in result.items()                          │
│    if k not in _EXCLUDED_STATE_KEYS                         │
│  }                                                           │
│  # 结果:                                                      │
│  state_update = {                                            │
│    files: {  # ✅ 包含subagent的所有文件修改!                  │
│      "/workspace/shared/task.txt": FileData(...),           │
│      "/workspace/tool_results/search.json": FileData(...), │
│      "/workspace/shared/result.json": FileData(...)         │
│    }                                                         │
│  }                                                           │
│                                                              │
│  return Command(update={                                     │
│    **state_update,  # files会被合并                          │
│    "messages": [ToolMessage(...)]  # 只返回最后一条消息       │
│  })                                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 状态合并(使用reducer)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              _file_data_reducer() 函数调用                    │
│  代码位置: virtual_filesystem/types.py:31-44                 │
│                                                              │
│  current = main_agent.state["files"]                        │
│  updates = subagent_result["files"]                         │
│                                                              │
│  merged = dict(current)  # 拷贝现有文件                       │
│  for path, data in updates.items():                         │
│    if data is None:                                          │
│      merged.pop(path, None)  # 删除文件                      │
│    else:                                                     │
│      merged[path] = data      # 更新/新增文件                │
│                                                              │
│  返回合并后的files字典                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 合并完成
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                Main Agent Runtime (更新后)                    │
│  State: {                                                    │
│    messages: [..., ToolMessage(...)],                       │
│    todos: [...],                                             │
│    files: {  # ✅ 包含了subagent的修改!                       │
│      "/workspace/shared/task.txt": FileData(...),           │
│      "/workspace/tool_results/search.json": FileData(...), │
│      "/workspace/shared/result.json": FileData(...)  # 新   │
│    }                                                         │
│  }                                                           │
│                                                              │
│  Main agent现在可以读取 result.json 了!                       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 关键代码位置

#### 2.2.1 状态准备(拷贝)

**文件**: [deepagents/libs/deepagents/deepagents/middleware/subagents.py:324-330](deepagents/libs/deepagents/deepagents/middleware/subagents.py#L324-L330)

```python
def _validate_and_prepare_state(
    subagent_type: str,
    description: str,
    runtime: ToolRuntime
) -> tuple[Runnable, dict]:
    """准备subagent调用的状态 - 创建状态拷贝。"""
    subagent = subagent_graphs[subagent_type]

    # 🔑 核心:拷贝所有状态,除了messages和todos
    subagent_state = {
        k: v for k, v in runtime.state.items()
        if k not in _EXCLUDED_STATE_KEYS
    }

    # 创建新的messages列表,只包含任务描述
    subagent_state["messages"] = [HumanMessage(content=description)]

    return subagent, subagent_state
```

#### 2.2.2 状态合并(返回)

**文件**: [deepagents/libs/deepagents/deepagents/middleware/subagents.py:315-322](deepagents/libs/deepagents/deepagents/middleware/subagents.py#L315-L322)

```python
def _return_command_with_state_update(result: dict, tool_call_id: str) -> Command:
    """返回包含状态更新的Command对象。"""

    # 🔑 核心:排除messages和todos,其他全部返回(包括files!)
    state_update = {
        k: v for k, v in result.items()
        if k not in _EXCLUDED_STATE_KEYS
    }

    return Command(
        update={
            **state_update,  # files等状态会被LangGraph使用reducer合并
            "messages": [ToolMessage(result["messages"][-1].text, tool_call_id=tool_call_id)],
        }
    )
```

#### 2.2.3 同步调用

**文件**: [deepagents/libs/deepagents/deepagents/middleware/subagents.py:339-352](deepagents/libs/deepagents/deepagents/middleware/subagents.py#L339-L352)

```python
def task(
    description: str,
    subagent_type: str,
    runtime: ToolRuntime,
) -> str | Command:
    if subagent_type not in subagent_graphs:
        allowed_types = ", ".join([f"`{k}`" for k in subagent_graphs])
        return f"We cannot invoke subagent {subagent_type}..."

    # 1. 准备:拷贝状态(除了messages/todos)
    subagent, subagent_state = _validate_and_prepare_state(
        subagent_type, description, runtime
    )

    # 2. 执行:使用拷贝的状态运行subagent
    result = subagent.invoke(subagent_state)

    if not runtime.tool_call_id:
        raise ValueError("Tool call ID is required for subagent invocation")

    # 3. 合并:返回状态更新,由LangGraph调用reducer合并
    return _return_command_with_state_update(result, runtime.tool_call_id)
```

---

## 三、Middleware注入机制

### 3.1 Runtime创建时的Middleware配置

**文件**: [src/components/deepagents/runtime.py:86-127](src/components/deepagents/runtime.py#L86-L127)

```python
def create_deep_agent_runtime(...) -> CompiledStateGraph:
    """创建配置好的deep agent runtime图。"""

    # ... 省略前面的配置 ...

    # 🔑 关键1: 构建subagent的默认middleware列表
    default_subagent_middleware: List[AgentMiddleware] = [
        JsonArgsParserMiddleware(enable_logging=True),
        TodoListMiddleware(),
    ]

    # ✅ 添加filesystem middleware给subagents
    # 这里使用了SAME middleware实例(或者相同配置的新实例)
    default_subagent_middleware.extend(provided_filesystem_middlewares)

    default_subagent_middleware.extend([
        SummarizationMiddleware(...),
        PatchToolCallsMiddleware(),
    ])

    # 🔑 关键2: 创建SubAgentMiddleware,传入default middleware
    subagent_middleware = SubAgentMiddleware(
        default_model=model,
        default_tools=tools or [],
        subagents=subagents or [],
        default_middleware=default_subagent_middleware,  # ← 包含filesystem middleware
        default_interrupt_on=interrupt_on,
        general_purpose_agent=True,
        task_description=subagents_cfg.get("task_description"),
    )

    # 🔑 关键3: 构建main agent的middleware列表
    deepagent_middleware: List[AgentMiddleware] = [
        JsonArgsParserMiddleware(enable_logging=True),
        TodoListMiddleware(),
    ]

    # ✅ 添加filesystem middleware给main agent
    deepagent_middleware.extend(provided_filesystem_middlewares)

    # 添加shell middleware
    if shell_middleware is not None:
        deepagent_middleware.append(shell_middleware)

    # 添加subagent middleware
    deepagent_middleware.append(subagent_middleware)
    # ... 其他middleware ...
```

**关键发现**:
1. **相同的filesystem middleware配置**被添加到:
   - Main agent的middleware列表 (line 127)
   - Subagents的默认middleware列表 (line 93)

2. 这意味着main agent和所有subagents都有**相同的filesystem工具**和**相同的状态schema**

### 3.2 Middleware实例化

**文件**: [src/components/deepagents/runtime.py:76-84](src/components/deepagents/runtime.py#L76-L84)

```python
# 如果没有提供filesystem middleware,则创建默认的VirtualFilesystemMiddleware
if isinstance(virtual_cfg, dict) and virtual_cfg.get("enabled", True):
    from .runtime_middlewares.virtual_filesystem import VirtualFilesystemMiddleware

    provided_filesystem_middlewares.append(
        VirtualFilesystemMiddleware(
            long_term_memory=use_long_term_memory or virtual_cfg.get("long_term_memory", False),
            tool_token_limit_before_evict=virtual_cfg.get("tool_token_limit_before_evict"),
        )
    )
```

**重要**: 这里创建的是**一个**`VirtualFilesystemMiddleware`实例,然后:
- 被添加到`provided_filesystem_middlewares`列表
- 这个列表被`extend`到main agent和subagents的middleware中

**问题**: 是同一个实例还是多个实例?

让我们看看`extend`的行为:

```python
# line 93
default_subagent_middleware.extend(provided_filesystem_middlewares)

# line 127
deepagent_middleware.extend(provided_filesystem_middlewares)
```

**答案**: `extend`只是将引用添加到列表中,所以main agent和subagents**共享同一个middleware实例**!

但是这**没有问题**,因为:
1. Middleware本身是无状态的(stateless)
2. 状态存储在LangGraph的state中,不在middleware中
3. Middleware只提供工具和系统提示

---

## 四、虚拟文件系统工具实现

### 4.1 工具列表

**文件**: [src/components/deepagents/runtime_middlewares/virtual_filesystem/tools.py:28-31](src/components/deepagents/runtime_middlewares/virtual_filesystem/tools.py#L28-L31)

```python
LIST_TOOL_NAME = "list_virtual_files"
READ_TOOL_NAME = "read_virtual_file"
WRITE_TOOL_NAME = "write_virtual_file"
EDIT_TOOL_NAME = "edit_virtual_file"
```

### 4.2 状态访问机制

所有工具都通过`ToolRuntime`访问状态:

```python
@tool(WRITE_TOOL_NAME)
def write_file(
    file_path: str,
    content: str,
    runtime: ToolRuntime[None, FilesystemState],  # ← 运行时注入
) -> Command | str:
    # runtime.state 包含当前agent的状态
    # 包括从main agent拷贝过来的files
    location = self.classify_path(file_path)

    if location.is_long_term:
        return self._write_file_to_store(runtime, path=location.path, content=content)

    # 写入state
    return self._write_file_to_state(runtime, path=location.path, content=content)
```

**关键**:
- Subagent的`runtime.state`包含从main agent拷贝的`files`
- 对`files`的修改会在subagent的状态中
- 当subagent返回时,修改会通过reducer合并回main agent

---

## 五、实际共享场景示例

### 5.1 场景:Main Agent委托Subagent处理任务

```python
# Main Agent执行流程:

# 1. Main agent写入任务描述到虚拟文件系统
write_virtual_file(
    "/workspace/shared/task_context.json",
    json.dumps({
        "objective": "分析API响应并提取关键指标",
        "api_response_file": "/workspace/tool_results/api_response.json"
    })
)
# State更新: files["/workspace/shared/task_context.json"] = FileData(...)

# 2. Main agent调用task工具委托给subagent
task(
    description="请分析 /workspace/shared/task_context.json 中指定的API响应",
    subagent_type="analyzer"
)

# --- 在task工具内部 ---

# 3. _validate_and_prepare_state() 拷贝状态
subagent_state = {
    # files字典被拷贝,包含:
    # - /workspace/shared/task_context.json
    # - /workspace/tool_results/api_response.json
    "files": main_agent.state["files"].copy(),  # 概念上的拷贝
    "messages": [HumanMessage("请分析...")]
}

# 4. Subagent执行
# Subagent可以:
# - 读取 /workspace/shared/task_context.json
# - 读取 /workspace/tool_results/api_response.json
# - 写入结果到 /workspace/shared/analysis_result.json

# 5. Subagent返回
subagent_result = {
    "messages": [..., AIMessage("分析完成")],
    "files": {
        "/workspace/shared/task_context.json": FileData(...),
        "/workspace/tool_results/api_response.json": FileData(...),
        "/workspace/shared/analysis_result.json": FileData(...)  # 新文件
    }
}

# 6. _return_command_with_state_update() 准备状态更新
state_update = {
    "files": subagent_result["files"]  # 包含新文件
}

# 7. LangGraph调用 _file_data_reducer()
merged_files = _file_data_reducer(
    current=main_agent.state["files"],
    updates=state_update["files"]
)
# merged_files 现在包含 analysis_result.json

# --- 回到Main Agent ---

# 8. Main agent可以读取subagent创建的文件
read_virtual_file("/workspace/shared/analysis_result.json")
# ✅ 成功读取!
```

### 5.2 路径约定

**文件**: [src/components/deepagents/runtime_middlewares/virtual_filesystem/middleware.py:24-45](src/components/deepagents/runtime_middlewares/virtual_filesystem/middleware.py#L24-L45)

系统提示建议的路径约定:

```
/workspace/tool_results/    - 大型工具输出 (如搜索结果)
/workspace/shared/          - Main agent和subagents之间共享的数据 ⭐
/workspace/processing/      - 中间计算结果
```

**最佳实践**: 使用`/workspace/shared/`目录存储需要在main agent和subagents之间传递的数据。

---

## 六、设计限制与注意事项

### 6.1 状态拷贝的性能影响

**潜在问题**:
- 每次调用subagent时,整个`files`字典被拷贝
- 如果虚拟文件系统很大(例如存储了大量工具结果),拷贝可能消耗内存

**缓解策略**:
1. 使用`tool_token_limit_before_evict`自动清理大文件
2. 只在虚拟文件系统中存储必要的数据
3. 考虑使用long-term memory(LangGraph Store)来存储大文件

### 6.2 并发修改问题

**场景**: 如果main agent和subagent同时修改同一个文件会怎样?

**答案**: **不会发生真正的并发修改**,因为:
1. Subagent是**同步调用**的(通过`invoke`或`ainvoke`)
2. Main agent在等待subagent返回时不会执行其他操作
3. 状态合并是**顺序的**:先拷贝,再执行,再合并

**但是**: 如果使用异步执行(例如`stream`模式),可能需要额外的协调机制。

### 6.3 文件冲突解决

**场景**: Subagent修改了一个文件,main agent也有该文件的旧版本

**当前行为**:
```python
# Reducer的行为
def _file_data_reducer(current, updates):
    merged = dict(current)
    for path, data in updates.items():
        if data is None:
            merged.pop(path, None)
        else:
            merged[path] = data  # ← 直接覆盖,无冲突检测
    return merged
```

**结论**:
- Subagent的修改会**覆盖**main agent的版本
- 没有版本控制或冲突检测
- 这是**Last Write Wins**策略

**建议**:
- 使用明确的文件命名约定避免冲突
- Subagent创建新文件而不是修改现有文件
- 使用时间戳或版本号在文件名中

### 6.4 状态排除键的硬编码

**文件**: [deepagents/libs/deepagents/deepagents/middleware/subagents.py:64](deepagents/libs/deepagents/deepagents/middleware/subagents.py#L64)

```python
_EXCLUDED_STATE_KEYS = ("messages", "todos")
```

**限制**:
- 这是硬编码的元组
- 如果添加其他需要隔离的状态字段,需要修改官方库
- 没有配置选项来自定义排除键

**影响**:
- 任何自定义状态字段(除了messages和todos)都会在agents之间共享
- 这可能不是期望的行为

---

## 七、官方实现vs自定义实现对比

### 7.1 官方SubAgentMiddleware

**特点**:
- ✅ 自动状态拷贝和合并
- ✅ 支持同步和异步调用
- ✅ 内置错误处理
- ✅ 统一的task工具接口
- ❌ 状态排除键硬编码
- ❌ 无法自定义状态传递逻辑

### 7.2 你的自定义实现

**文件**: [src/components/deepagents/runtime_middlewares/subagents/middleware.py:234-267](src/components/deepagents/runtime_middlewares/subagents/middleware.py#L234-L267)

```python
async def invoke_task(subagent_type: str, description: str) -> str:
    """调用subagent处理特定任务。"""
    if subagent_type not in self._subagent_runnables:
        return f"Error: Unknown subagent type '{subagent_type}'..."

    subagent = self._subagent_runnables[subagent_type]
    try:
        # ⚠️ 问题:只传递messages,不传递files!
        result = await subagent.ainvoke({
            "messages": [{"role": "user", "content": description}]
        })
        messages = result.get("messages", [])
        if messages:
            response = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
            return response
        return "SubAgent completed but returned no response."
    except Exception as exc:
        return f"SubAgent execution failed: {exc}"
```

**问题**:
- ❌ **不传递`files`状态!**
- ❌ 不合并返回的状态
- ❌ 只返回文本响应,不返回Command对象

**结果**:
- Subagent无法访问main agent的虚拟文件系统
- Subagent的文件修改不会合并回main agent
- 虚拟文件系统在agents之间**完全隔离**

---

## 八、如何实现真正的共享

### 8.1 方案1: 使用官方SubAgentMiddleware (推荐)

**优点**:
- ✅ 开箱即用
- ✅ 自动状态拷贝和合并
- ✅ 虚拟文件系统自动共享
- ✅ 经过测试和验证

**实现**:
```python
# 在 create_deep_agent_runtime() 中已经正确配置了!
# 只需确保:
# 1. 使用官方的 SubAgentMiddleware (从deepagents.middleware.subagents导入)
# 2. 不要使用自定义的 invoke_task 实现
# 3. 让agent使用 task 工具而不是自定义工具

# Main agent调用:
task(
    description="请处理这个任务",
    subagent_type="worker"
)
# ✅ 虚拟文件系统自动共享!
```

### 8.2 方案2: 修复自定义实现

如果必须使用自定义实现,需要修改`invoke_task`:

```python
async def invoke_task(
    subagent_type: str,
    description: str,
    runtime: ToolRuntime[None, FilesystemState],  # ← 需要runtime参数
) -> Command | str:  # ← 返回Command而不是str
    """调用subagent处理特定任务 - 支持状态共享。"""
    if subagent_type not in self._subagent_runnables:
        return f"Error: Unknown subagent type '{subagent_type}'..."

    subagent = self._subagent_runnables[subagent_type]
    try:
        # ✅ 拷贝状态,排除messages和todos
        subagent_state = {
            k: v for k, v in runtime.state.items()
            if k not in ("messages", "todos")
        }
        # 创建新的messages
        subagent_state["messages"] = [{"role": "user", "content": description}]

        # 执行subagent
        result = await subagent.ainvoke(subagent_state)

        # ✅ 准备状态更新
        state_update = {
            k: v for k, v in result.items()
            if k not in ("messages", "todos")
        }

        # 提取响应消息
        messages = result.get("messages", [])
        response_text = ""
        if messages:
            last_msg = messages[-1]
            response_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

        # ✅ 返回Command对象进行状态合并
        if not runtime.tool_call_id:
            # 如果没有tool_call_id,只返回文本
            return response_text

        return Command(
            update={
                **state_update,  # 包含files的修改
                "messages": [ToolMessage(response_text, tool_call_id=runtime.tool_call_id)],
            }
        )
    except Exception as exc:
        return f"SubAgent execution failed: {exc}"
```

**关键修改**:
1. 添加`runtime: ToolRuntime`参数获取当前状态
2. 拷贝状态时排除messages和todos
3. 返回`Command`对象而不是字符串
4. Command的update包含files等状态修改

### 8.3 方案3: Long-Term Memory (跨会话共享)

如果需要在不同会话或不同agent实例之间共享文件:

```python
# 配置long-term memory
VirtualFilesystemMiddleware(
    long_term_memory=True,  # ← 启用持久化
    tool_token_limit_before_evict=20000,
)

# 使用 /memories/ 前缀访问持久化存储
write_virtual_file(
    "/memories/shared/persistent_data.json",
    json.dumps({"key": "value"})
)

# 这个文件会存储在LangGraph Store中
# 可以跨会话、跨agent实例访问
```

**存储位置**: LangGraph Store (需要配置checkpointer和store)

---

## 九、推荐的最佳实践

### 9.1 使用官方SubAgentMiddleware

```python
# ✅ 推荐
from deepagents.middleware.subagents import SubAgentMiddleware

# 在 create_deep_agent_runtime() 中已经正确配置
# 不需要额外修改
```

### 9.2 明确的文件路径约定

```python
# Main agent写入任务上下文
write_virtual_file(
    "/workspace/shared/task_{task_id}.json",  # 使用唯一ID
    json.dumps(task_context)
)

# Subagent读取和写入
read_virtual_file("/workspace/shared/task_{task_id}.json")
write_virtual_file(
    "/workspace/shared/result_{task_id}.json",  # 新文件,避免冲突
    json.dumps(result)
)

# Main agent读取结果
read_virtual_file("/workspace/shared/result_{task_id}.json")
```

### 9.3 大文件管理

```python
# ✅ 好: 将大型工具结果存储在虚拟文件系统
search_results = tavily_search(query)
write_virtual_file(
    "/workspace/tool_results/search_{timestamp}.json",
    json.dumps(search_results)
)

# Agent只处理文件路径,不处理大型数据结构
task(
    description=f"请分析文件 /workspace/tool_results/search_{timestamp}.json",
    subagent_type="analyzer"
)
```

### 9.4 清理策略

```python
# 配置自动清理
VirtualFilesystemMiddleware(
    tool_token_limit_before_evict=20000,  # 超过20k token自动清理
)

# 或手动删除不再需要的文件
# (需要实现delete工具,当前没有)
```

### 9.5 错误处理

```python
# Main agent
try:
    result = task(
        description="处理任务",
        subagent_type="worker"
    )

    # 检查结果中是否有错误标记
    if isinstance(result, str) and "Error" in result:
        # 处理错误
        pass
except Exception as e:
    # 处理异常
    pass
```

---

## 十、总结与建议

### 10.1 核心发现总结

| 问题 | 答案 |
|------|------|
| 虚拟文件系统是否支持多agent共享? | ✅ **支持**,通过状态拷贝+reducer合并 |
| 是否需要修改官方实现? | ❌ **不需要**,官方实现已经支持 |
| 你的自定义实现是否支持共享? | ❌ **不支持**,需要修改 |
| 共享机制是什么? | 状态拷贝 → subagent执行 → reducer合并 |
| 是否为真正的引用共享? | ❌ 是拷贝共享,非引用共享 |
| 是否有并发问题? | ❌ 同步执行,无并发问题 |
| 是否有冲突检测? | ❌ Last Write Wins,无冲突检测 |
| 如何实现持久化共享? | 使用long-term memory + /memories/路径 |

### 10.2 关键代码位置汇总

| 功能 | 文件路径 | 行号 |
|------|----------|------|
| 状态reducer | [src/components/deepagents/runtime_middlewares/virtual_filesystem/types.py](src/components/deepagents/runtime_middlewares/virtual_filesystem/types.py) | 31-44 |
| 状态排除键 | [deepagents/libs/deepagents/deepagents/middleware/subagents.py](deepagents/libs/deepagents/deepagents/middleware/subagents.py#L64) | 64 |
| 状态拷贝 | [deepagents/libs/deepagents/deepagents/middleware/subagents.py](deepagents/libs/deepagents/deepagents/middleware/subagents.py#L324-L330) | 324-330 |
| 状态合并 | [deepagents/libs/deepagents/deepagents/middleware/subagents.py](deepagents/libs/deepagents/deepagents/middleware/subagents.py#L315-L322) | 315-322 |
| Runtime创建 | [src/components/deepagents/runtime.py](src/components/deepagents/runtime.py#L86-L127) | 86-127 |
| Middleware注入 | [src/components/deepagents/runtime.py](src/components/deepagents/runtime.py#L92-L93) | 92-93 |
| 自定义实现(有问题) | [src/components/deepagents/runtime_middlewares/subagents/middleware.py](src/components/deepagents/runtime_middlewares/subagents/middleware.py#L234-L267) | 234-267 |

### 10.3 行动建议

#### 短期 (立即执行)

1. **✅ 验证官方实现已启用**
   - 检查`create_deep_agent_runtime()`是否使用了官方`SubAgentMiddleware`
   - 确认filesystem middleware已添加到main agent和subagents

2. **✅ 添加测试用例**
   - 测试main agent写入文件 → subagent读取
   - 测试subagent写入文件 → main agent读取
   - 测试文件修改和删除

3. **✅ 更新文档**
   - 记录`/workspace/shared/`路径约定
   - 说明虚拟文件系统在agents之间的共享机制
   - 添加使用示例

#### 中期 (1-2周)

1. **🔧 决定自定义实现的去留**
   - 如果不需要特殊功能,删除自定义`invoke_task`
   - 如果需要保留,按照方案2修复状态共享问题

2. **📊 监控性能**
   - 监控大文件拷贝的性能影响
   - 调整`tool_token_limit_before_evict`参数
   - 考虑实现文件清理工具

3. **🔒 增强错误处理**
   - 添加文件路径验证
   - 添加状态大小检查
   - 实现优雅的错误恢复

#### 长期 (1个月+)

1. **🚀 考虑优化方案**
   - 实现增量状态传递(只传递变更)
   - 添加版本控制或冲突检测
   - 支持可配置的状态排除键

2. **📈 扩展功能**
   - 实现文件删除工具
   - 添加文件元数据查询
   - 支持文件搜索和过滤

3. **🔄 与上游同步**
   - 跟踪deepagents库的更新
   - 提交PR改进官方实现
   - 参与社区讨论

### 10.4 风险评估

| 风险 | 严重性 | 可能性 | 缓解措施 |
|------|--------|--------|----------|
| 大文件拷贝性能问题 | 中 | 中 | 使用tool_token_limit,监控性能 |
| 文件冲突覆盖 | 中 | 低 | 使用唯一文件名,添加时间戳 |
| 自定义实现不兼容 | 高 | 高 | 修复或删除自定义实现 |
| 状态大小超限 | 中 | 低 | 定期清理,使用long-term memory |
| 官方库API变更 | 低 | 低 | 锁定版本,定期检查更新 |

---

## 十一、实例代码

### 11.1 正确使用官方实现

```python
from deepagents.runtime import create_deep_agent_runtime
from deepagents.middleware.subagents import SubAgent

# 定义subagents
subagents = [
    SubAgent(
        name="analyzer",
        description="分析数据并生成报告",
        tools=[...],
    ),
    SubAgent(
        name="researcher",
        description="研究和收集信息",
        tools=[...],
    ),
]

# 创建runtime(已包含正确的filesystem middleware配置)
runtime = create_deep_agent_runtime(
    model="gpt-4",
    system_prompt="你是一个协调型AI助手",
    tools=[...],
    middleware_config={
        "filesystem": {
            "virtual": {
                "enabled": True,
                "long_term_memory": False,
                "tool_token_limit_before_evict": 20000,
            }
        }
    },
    subagents=subagents,
    use_long_term_memory=False,
)

# Main agent使用示例
async def main():
    # 1. Main agent写入共享文件
    await runtime.ainvoke({
        "messages": [{
            "role": "user",
            "content": "请分析这些数据: [large_dataset]"
        }]
    })

    # Agent内部逻辑:
    # - 使用 write_virtual_file("/workspace/shared/dataset.json", ...)
    # - 调用 task("分析dataset.json", "analyzer")
    # - Subagent读取dataset.json
    # - Subagent写入 analysis_result.json
    # - Main agent读取 analysis_result.json

    # ✅ 虚拟文件系统在整个过程中自动共享!
```

### 11.2 Main Agent提示词示例

```python
MAIN_AGENT_PROMPT = """你是一个协调型AI助手,可以委托专门的子代理处理复杂任务。

虚拟文件系统使用指南:
1. 使用 /workspace/shared/ 存储需要与子代理共享的数据
2. 使用 /workspace/tool_results/ 存储大型工具输出
3. 使用唯一的文件名避免冲突(如加时间戳)

工作流程:
1. 将任务上下文写入 /workspace/shared/task_<id>.json
2. 使用task工具调用适当的子代理
3. 子代理会读取任务文件,处理后写入结果
4. 读取结果文件 /workspace/shared/result_<id>.json

示例:
```
# 步骤1: 准备任务数据
write_virtual_file("/workspace/shared/task_001.json", ...)

# 步骤2: 委托给子代理
task(
    description="请处理文件 /workspace/shared/task_001.json 中的任务",
    subagent_type="analyzer"
)

# 步骤3: 读取结果
read_virtual_file("/workspace/shared/result_001.json")
```

可用的子代理:
{available_subagents}
"""
```

### 11.3 Subagent提示词示例

```python
ANALYZER_SUBAGENT_PROMPT = """你是一个数据分析专家。

你可以访问虚拟文件系统,特别是:
- /workspace/shared/ - 主代理共享给你的任务数据
- /workspace/processing/ - 存储中间处理结果

工作流程:
1. 从任务描述中找到输入文件路径
2. 读取输入文件
3. 执行分析
4. 将结果写入 /workspace/shared/result_<task_id>.json

文件命名约定:
- 使用与任务ID匹配的result文件名
- 例如: task_001.json → result_001.json
"""
```

---

## 十二、测试计划

### 12.1 单元测试

```python
import pytest
from your_module import create_deep_agent_runtime

@pytest.mark.asyncio
async def test_virtual_filesystem_sharing_between_agents():
    """测试虚拟文件系统在main agent和subagent之间的共享。"""

    # 创建runtime
    runtime = create_deep_agent_runtime(
        model="gpt-4",
        system_prompt="测试助手",
        tools=[],
        middleware_config={
            "filesystem": {
                "virtual": {"enabled": True}
            }
        },
        subagents=[
            SubAgent(
                name="worker",
                description="工作子代理",
                tools=[],
            )
        ],
    )

    # 模拟main agent写入文件并调用subagent
    result = await runtime.ainvoke({
        "messages": [{
            "role": "user",
            "content": """
            请执行以下步骤:
            1. 写入文件 /workspace/shared/test.txt,内容为"Hello"
            2. 使用task工具调用worker子代理,让它读取并修改这个文件
            3. 读取修改后的文件
            """
        }]
    })

    # 验证:
    # - subagent能读取main agent写入的文件
    # - main agent能读取subagent修改的文件
    assert "成功" in result["messages"][-1].content

@pytest.mark.asyncio
async def test_file_data_reducer():
    """测试文件数据reducer的合并逻辑。"""
    from src.components.deepagents.runtime_middlewares.virtual_filesystem.types import (
        _file_data_reducer,
        FileData,
    )

    # 初始状态
    current = {
        "/file1.txt": FileData(
            content=["line1"],
            created_at="2024-01-01T00:00:00",
            modified_at="2024-01-01T00:00:00"
        ),
        "/file2.txt": FileData(
            content=["line2"],
            created_at="2024-01-01T00:00:00",
            modified_at="2024-01-01T00:00:00"
        ),
    }

    # 更新(新增、修改、删除)
    updates = {
        "/file1.txt": FileData(  # 修改
            content=["modified"],
            created_at="2024-01-01T00:00:00",
            modified_at="2024-01-02T00:00:00"
        ),
        "/file2.txt": None,  # 删除
        "/file3.txt": FileData(  # 新增
            content=["new"],
            created_at="2024-01-02T00:00:00",
            modified_at="2024-01-02T00:00:00"
        ),
    }

    # 合并
    merged = _file_data_reducer(current, updates)

    # 验证
    assert "/file1.txt" in merged
    assert merged["/file1.txt"]["content"] == ["modified"]
    assert "/file2.txt" not in merged  # 已删除
    assert "/file3.txt" in merged
    assert merged["/file3.txt"]["content"] == ["new"]
```

### 12.2 集成测试

```python
@pytest.mark.asyncio
async def test_end_to_end_multi_agent_workflow():
    """端到端测试:main agent → subagent → main agent的完整工作流。"""

    runtime = create_deep_agent_runtime(...)

    # 步骤1: Main agent处理用户请求
    result1 = await runtime.ainvoke({
        "messages": [{
            "role": "user",
            "content": "请分析这个API响应并提取错误信息: {api_response}"
        }]
    })

    # 验证main agent写入了文件
    state1 = result1
    assert "/workspace/shared/api_response.json" in state1.get("files", {})

    # 步骤2: 继续对话,触发subagent调用
    result2 = await runtime.ainvoke({
        "messages": result1["messages"] + [{
            "role": "user",
            "content": "现在使用analyzer子代理来分析这个响应"
        }]
    })

    # 验证subagent创建了结果文件
    state2 = result2
    assert "/workspace/shared/analysis_result.json" in state2.get("files", {})

    # 验证main agent能读取结果
    final_message = result2["messages"][-1].content
    assert "分析完成" in final_message or "错误" in final_message
```

---

## 附录A: 文件路径速查表

| 组件 | 文件路径 |
|------|----------|
| 虚拟文件系统Middleware | [src/components/deepagents/runtime_middlewares/virtual_filesystem/middleware.py](src/components/deepagents/runtime_middlewares/virtual_filesystem/middleware.py) |
| 类型定义和Reducer | [src/components/deepagents/runtime_middlewares/virtual_filesystem/types.py](src/components/deepagents/runtime_middlewares/virtual_filesystem/types.py) |
| 文件系统工具 | [src/components/deepagents/runtime_middlewares/virtual_filesystem/tools.py](src/components/deepagents/runtime_middlewares/virtual_filesystem/tools.py) |
| 工具辅助函数 | [src/components/deepagents/runtime_middlewares/virtual_filesystem/utils.py](src/components/deepagents/runtime_middlewares/virtual_filesystem/utils.py) |
| 服务层配置 | [src/application/services/agent/deep/middleware/virtual_filesystem_service.py](src/application/services/agent/deep/middleware/virtual_filesystem_service.py) |
| Runtime创建 | [src/components/deepagents/runtime.py](src/components/deepagents/runtime.py) |
| 官方SubAgent实现 | [deepagents/libs/deepagents/deepagents/middleware/subagents.py](deepagents/libs/deepagents/deepagents/middleware/subagents.py) |
| 自定义SubAgent(待修复) | [src/components/deepagents/runtime_middlewares/subagents/middleware.py](src/components/deepagents/runtime_middlewares/subagents/middleware.py) |
| 配置文件 | [config/agents/deep/middleware/filesystem/virtual_filesystem.json](config/agents/deep/middleware/filesystem/virtual_filesystem.json) |

---

## 附录B: 关键概念术语表

| 术语 | 定义 |
|------|------|
| **AgentState** | LangGraph中agent的状态schema,定义可用的状态字段 |
| **Reducer** | 状态合并函数,定义如何合并来自不同执行步骤的状态更新 |
| **Middleware** | 为agent添加功能的组件(工具、系统提示、状态schema) |
| **FileData** | 虚拟文件的序列化表示,包含content、created_at、modified_at |
| **FilesystemState** | 扩展AgentState,添加files字段及其reducer |
| **ToolRuntime** | 工具执行时的运行时上下文,提供对当前状态的访问 |
| **Command** | LangGraph的命令对象,用于返回状态更新 |
| **State Copying** | 将main agent的状态拷贝给subagent的过程 |
| **State Merging** | 将subagent的状态更新合并回main agent的过程 |
| **Excluded Keys** | 在状态拷贝/合并时排除的键(messages, todos) |
| **Long-Term Memory** | 使用LangGraph Store实现的持久化存储 |
| **Last Write Wins** | 冲突解决策略:最后一次写入覆盖之前的值 |

---

## 附录C: 调试检查清单

当虚拟文件系统在agents之间共享出现问题时,按以下顺序检查:

- [ ] **1. 确认使用官方SubAgentMiddleware**
  - 检查导入: `from deepagents.middleware.subagents import SubAgentMiddleware`
  - 不是自定义实现

- [ ] **2. 确认filesystem middleware已注入**
  - 检查`create_deep_agent_runtime()`的配置
  - 确认`provided_filesystem_middlewares`被添加到main agent和subagents

- [ ] **3. 确认状态拷贝逻辑**
  - 检查`_validate_and_prepare_state()`是否正确拷贝状态
  - 确认`files`键不在`_EXCLUDED_STATE_KEYS`中

- [ ] **4. 确认状态合并逻辑**
  - 检查`_return_command_with_state_update()`是否返回Command对象
  - 确认返回的update包含files字段

- [ ] **5. 确认reducer正确注册**
  - 检查`FilesystemState`定义
  - 确认`files`字段使用`Annotated[..., _file_data_reducer]`

- [ ] **6. 检查文件路径**
  - 使用`/workspace/shared/`前缀
  - 避免使用`/memories/`前缀(除非启用long-term memory)
  - 文件名唯一,避免冲突

- [ ] **7. 检查工具调用**
  - Main agent使用`task(description, subagent_type)`
  - 不是自定义的`invoke_task`

- [ ] **8. 检查日志**
  - 启用debug模式
  - 查看状态拷贝和合并的日志
  - 检查是否有异常或错误

- [ ] **9. 验证配置**
  - 检查`virtual_filesystem.json`
  - 确认`enabled: true`
  - 检查token限制设置

- [ ] **10. 测试简化场景**
  - 创建最小可复现示例
  - 一个main agent,一个subagent
  - 一个简单的文件写入和读取操作

---

**文档版本**: 1.0
**创建日期**: 2025-01-17
**最后更新**: 2025-01-17
**作者**: Claude (Anthropic)
**审阅状态**: 待审阅
