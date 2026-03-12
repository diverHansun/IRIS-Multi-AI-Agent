# Deep Agent 消息显示优化实施计划

> **文档定位**: 实施步骤文档，定义修改清单、执行约束与验证方案。
>
> **关联文档**:
> [problem-analysis.md](./problem-analysis.md) -- 问题诊断（现象、根因链路、代码级分析）
> [design-proposal.md](./design-proposal.md) -- 方案设计（显示通道分离、样式策略）

---

## 1. 修改文件清单

共 2 个文件，均位于 `src/application/services/agent/deep/streaming/`:

| 序号 | 文件 | 修改类型 | 影响范围 |
|------|------|---------|---------|
| 1 | `event_handler.py` | 逻辑改造 | Step 描述、文本 flush、状态追踪 |
| 2 | `conversation.py` | 条件输出 | 最终输出去重 |

### 1.1 步骤依赖关系

```
步骤 1 (_describe_messages 改造)  ─┐
                                   │
步骤 2 (flush 状态追踪)            ─┼── 步骤 5 (conversation.py 去重)
                                   │
步骤 3 (flush 样式区分)            ─┤
                                   │
步骤 4 (flush 触发点适配)          ─┘
```

步骤 1-4 均修改 `event_handler.py`，步骤 5 修改 `conversation.py` 且依赖步骤 2 引入的
`has_streamed_answer()` 判定能力。

**推荐执行顺序**: 1 -> 2 -> 3 -> 4 -> 5

---

## 2. 各步骤详细修改

### 步骤一: 改造 `_describe_messages()` -- Step 行去除 AI 文本内容

**文件**: `src/application/services/agent/deep/streaming/event_handler.py`
**方法**: `_describe_messages()`

**改造内容**:

```python
# 改造前:
if isinstance(last_message, AIMessage):
    content_snippet = self._truncate(str(last_message.content))
    if last_message.tool_calls and self.show_tool_calls:
        tool_names = {
            call.get("name", "unknown") for call in last_message.tool_calls
        }
        tools = ", ".join(sorted(tool_names))
        return f"{node}: Calling tools [{tools}]"
    return f"{node}: {content_snippet}"

# 改造后:
if isinstance(last_message, AIMessage):
    if last_message.tool_calls and self.show_tool_calls:
        tool_names = {
            call.get("name", "unknown") for call in last_message.tool_calls
        }
        tools = ", ".join(sorted(tool_names))
        return f"{node}: Calling tools [{tools}]"
    content = str(last_message.content).strip()
    if not content:
        return None
    return f"{node}: Thinking"
```

**验证**: 运行 deep agent 查询，Step 行中不再出现 AI 文本内容片段，
纯文本 AIMessage 显示为 `"model: Thinking"`。

---

### 步骤二: 引入最终答案匹配状态

**文件**: `src/application/services/agent/deep/streaming/event_handler.py`
**位置**: `__init__()` 及新增属性

**改造内容**:

在 `__init__()` 中新增实例变量:

```python
self._last_flushed_text: str = ""
self._last_flush_kind: str | None = None
```

新增判定方法:

```python
def has_streamed_answer(self, answer: str) -> bool:
    """Return whether the final answer has already been streamed."""
    return (
        self._last_flush_kind == "message_end"
        and self._last_flushed_text.strip() == answer.strip()
    )
```

---

### 步骤三: 改造 `_flush_text_buffer()` -- 样式区分与前缀统一

**文件**: `src/application/services/agent/deep/streaming/event_handler.py`
**方法**: `_flush_text_buffer()`

**改造内容**:

```python
# 改造前:
def _flush_text_buffer(self, *, final: bool = False) -> None:
    if not final or not self._pending_text.strip():
        return

    self._stop_spinner()

    if not self._has_responded:
        self.console.print("Agent:", style=f"bold {COLORS['agent']}", markup=False)
        self._has_responded = True

    self.console.print(
        escape(self._pending_text.rstrip()),
        style=COLORS["text_primary"],
    )
    self._pending_text = ""

# 改造后:
def _flush_text_buffer(self, *, final: bool = False, flush_kind: str = "message_end") -> None:
    if not final or not self._pending_text.strip():
        return

    self._stop_spinner()
    text = self._pending_text.rstrip()
    self._last_flushed_text = text
    self._last_flush_kind = flush_kind
    self._has_responded = True

    if flush_kind == "tool_call":
        text_style = "dim"
    else:
        text_style = COLORS["text_primary"]

    self.console.print(
        f"[bold {COLORS['agent']}]DeepAgent >[/] ",
        end="",
    )
    self.console.print(
        escape(text),
        style=text_style,
    )
    self._pending_text = ""
```

**关键变更说明**:
- 新增 `flush_kind` 参数，取值 `"tool_call"` / `"message_end"`
- 前缀从 `"Agent:"` 改为 `"DeepAgent >"`，与最终输出标记一致
- 每次 flush 都带前缀，不再依赖 `_has_responded` 控制前缀显示
- 记录最后一次 flush 的文本内容及来源，供最终答案去重使用
- `_has_responded` 保留以避免影响其他依赖该标志的逻辑

---

### 步骤四: 适配 flush 触发点

**文件**: `src/application/services/agent/deep/streaming/event_handler.py`

需修改 3 个调用点:

**4.1 `_try_display_tool_call()` -- 中间文本 flush**

```python
# 改造前:
self._flush_text_buffer(final=True)

# 改造后:
self._flush_text_buffer(final=True, flush_kind="tool_call")
```

**4.2 `_process_direct_tool_call()` -- direct tool call 前 flush**

```python
def _process_direct_tool_call(self, tool_call):
    ...
    self._flush_text_buffer(final=True, flush_kind="tool_call")
    ...
```

此处不能只补 flush，还需配合步骤 4.4 的顺序调整，否则仍会被 `message_end` 路径抢先 flush。

**4.3 `_process_ai_message_content_blocks()` -- 消息结束 flush**

```python
# 改造前:
if getattr(message, "chunk_position", None) == "last":
    self._flush_text_buffer(final=True)

# 改造后:
if getattr(message, "chunk_position", None) == "last":
    self._flush_text_buffer(final=True, flush_kind="message_end")
```

**4.4 `_process_ai_message_content_blocks()` -- 工具调用处理顺序调整**

当前顺序是：

```python
content_blocks -> message_end flush -> direct tool_calls
```

需要改为：

```python
content_blocks(text/reasoning/tool_call_chunk/tool_call)
    -> fallback direct tool_calls
    -> message_end flush
```

**实现约束**:
- `tool_call_chunk` 与 `tool_call` 都必须纳入处理
- `message.tool_calls` 仅作为 fallback，避免与 `content_blocks` 双重渲染
- `message_end` flush 必须发生在所有工具调用处理之后

---

### 步骤五: 改造 `conversation.py` 最终输出 -- 条件去重

**文件**: `src/application/services/agent/deep/streaming/conversation.py`
**位置**: `handle_deep_agent_query()` 末尾输出区

**改造内容**:

```python
# 改造前:
answer = result.get("output", "No response generated.")
ctx.console.print(f"[bold blue]DeepAgent >[/] {escape(answer)}")

# 改造后:
answer = result.get("output", "No response generated.")
if not event_handler.has_streamed_answer(answer):
    ctx.console.print(f"[bold blue]DeepAgent >[/] {escape(answer)}")
```

**验证**:
- 当最后一次 `"message_end"` flush 已输出与 `answer` 一致的文本时，流结束后不再重复打印
- 当 messages 流无输出，或只输出了中间文本时，完整回答仍正常打印

---

## 3. 执行约束

### 3.1 不修改的部分

以下逻辑在本次改造中保持不变:

- `_render_update()`: Step 行的格式化和输出机制
- `_capture_state()`: 状态捕获逻辑
- `_track_tool_usage()`: 工具使用统计
- `_process_tool_message()`: 工具消息处理和显示
- `_render_tool_call()`: 工具调用显示
- `render_summary()`: 执行摘要显示
- `prepare_stream_result()`: 最终结果数据提取
- HITL 中断/恢复流程
- 消息持久化逻辑
- `namespace` / subgraph 过滤
- summarization metadata 过滤

### 3.2 向后兼容

- `_flush_text_buffer()` 新增的 `flush_kind` 参数有默认值 `"message_end"`，
  现有未指定该参数的调用方行为与改造前一致
- `_has_responded` 标志保留，避免影响其他可能依赖该标志的逻辑
- `has_streamed_answer()` 为新增判定方法，不影响现有接口

---

## 4. 验证方案

### 4.1 手工验证场景

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 简单查询 | 发送不需要工具调用的问题 | `DeepAgent >` 正常样式输出，无 Step 内容泄露 |
| 工具调用查询 | 发送需要搜索的问题 | 中间文本 dim 样式，最终输出正常样式，Step 行显示 "Thinking" |
| 多轮工具调用 | 发送需要多次搜索的复杂问题 | 每次中间文本都带 `DeepAgent >` 前缀 + dim 样式 |
| 仅中间文本被 flush | 模拟 direct tool call 或异常流式顺序 | `conversation.py` 仍会输出最终答案，不会因中间文本错误去重 |
| 无 content_blocks | 使用不支持 content_blocks 的模型 | `has_streamed_answer(answer) == False`，conversation.py 保底输出 |
| 空回复 | 模型返回空内容 | Step 行中空 AIMessage 被跳过，flush 不触发 |

### 4.2 回归验证

- HITL 中断/恢复流程不受影响
- 工具调用显示（Tool: ...）格式不变
- 执行摘要（Summary）正常显示
- 会话持久化正常工作

---

## 5. 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| messages 流行为因模型不同而异 | 中 | 仅在最后一次 `"message_end"` flush 与最终答案匹配时才跳过回退输出 |
| `chunk_position` 属性可能不存在 | 低 | 使用 `getattr(message, "chunk_position", None)` 安全访问 |
| Rich console markup 在前缀中的转义 | 低 | 前缀使用 Rich markup 语法，内容使用 `escape()` |
| `_has_responded` 语义变化 | 低 | 保留该标志的赋值，维持现有依赖方的预期 |
