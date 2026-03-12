# Deep Agent 消息显示优化设计方案

> **文档定位**: 方案设计文档，定义显示通道分离策略、样式规则与状态管理。
>
> **关联文档**:
> [problem-analysis.md](./problem-analysis.md) -- 问题诊断（现象、根因链路、代码级分析）
> [implementation-plan.md](./implementation-plan.md) -- 实施步骤（修改清单、验证方案）

---

## 1. 设计目标

1. Step 行仅做状态追踪，不泄露 AI 文本内容
2. 中间文本与最终输出通过 messages 流完整显示，并以样式区分
3. 消除最终回答的重复输出
4. 当 messages 流未产生输出时，保留回退通道保证内容可见

## 2. 设计原则

| 原则 | 应用 |
|------|------|
| **单一职责 (SRP)** | updates 流负责状态追踪，messages 流负责文本展示，职责不交叉 |
| **关注点分离** | Step 行是结构化状态信息，AI 文本是内容信息，两者在不同通道显示 |
| **优雅降级** | messages 流异常时，conversation.py 保底输出确保内容不丢失 |
| **最小修改** | 仅修改显示层逻辑，不改变消息处理、持久化、HITL 等核心流程 |

---

## 3. 显示通道分离架构

### 3.1 改造前后对比

**改造前** -- 职责混杂:

```
updates 流 (Step 行):  状态追踪 + AI 文本截断       <-- 职责混杂
messages 流 (flush):   AI 文本完整展示 ("Agent:")
conversation.py:       AI 文本完整展示 ("DeepAgent >") <-- 与 flush 重复
```

**改造后** -- 职责分离:

```
updates 流 (Step 行):  纯状态追踪（功能性描述）       <-- 不含 AI 文本
messages 流 (flush):   AI 文本完整展示 ("DeepAgent >") <-- 区分中间/最终样式
conversation.py:       仅在 messages 流未输出时保底     <-- 条件输出，消除重复
```

### 3.2 数据流设计

```
                 messages 流                          updates 流
                    |                                     |
         _pending_text 累积                        _describe_messages()
                    |                                     |
         _flush_text_buffer()                     _render_update()
                    |                                     |
         判断 flush 触发源:                       纯状态描述:
         +-- tool call 触发                       "model: Thinking"
         |   --> dim 样式                         "model: Calling tools [...]"
         |   --> "DeepAgent >"                    "tools: Tool 'x' completed."
         |   --> 记录 last_flushed_text/last_flush_kind
         |
         +-- chunk_position=="last" 触发
             --> 正常样式
             --> "DeepAgent >"
             --> 记录 last_flushed_text/last_flush_kind
                    |
                    +--- 流结束后 ---+
                                     |
                         conversation.py 检查:
                         has_streamed_answer(answer) == True?
                         +-- 是: 跳过完整输出
                         +-- 否: 保底完整输出
```

---

## 4. 具体设计

### 4.1 Step 行描述改造

**变更对象**: `_describe_messages()` 方法

**规则**: 当 AIMessage 不含 `tool_calls` 时，返回功能性描述 `"Thinking"` 替代截断内容。

| 消息类型 | 改造前 | 改造后 |
|---------|--------|--------|
| AIMessage + tool_calls | `"model: Calling tools [web_search]"` | 不变 |
| AIMessage 纯文本 | `"model: 基于我的并行搜索结果..."` (截断) | `"model: Thinking"` |
| AIMessage 空内容 | `"model: "` | 返回 `None`（跳过该 Step） |
| ToolMessage | `"tools: Tool 'x' completed."` | 不变 |

**伪代码**:

```python
def _describe_messages(self, node, messages):
    last_message = messages[-1]

    if isinstance(last_message, ToolMessage):
        # 不变
        ...

    if isinstance(last_message, AIMessage):
        if last_message.tool_calls and self.show_tool_calls:
            # 不变: 显示工具调用列表
            ...
            return f"{node}: Calling tools [{tools}]"
        # 改造: 纯文本 AIMessage 用功能性描述替代内容截断
        content = str(last_message.content).strip()
        if not content:
            return None  # 空消息跳过
        return f"{node}: Thinking"
```

### 4.2 文本 flush 样式区分

**变更对象**: `_flush_text_buffer()` 方法及相关调用路径

**设计要点**:

1. 引入 `flush_kind` 参数区分触发来源
2. 记录最后一次 flush 的文本内容与来源，而不是仅记录“是否输出过任意文本”
3. 前缀统一使用 `"DeepAgent >"` 替代 `"Agent:"`
4. 每次 flush 都带前缀

**flush 触发源与样式映射**:

| 触发源 | 调用路径 | 含义 | 前缀 | 样式 |
|--------|---------|------|------|------|
| `"tool_call"` | `_try_display_tool_call()` 调用 flush | 中间思考，后面紧跟工具调用 | `DeepAgent >` | dim |
| `"message_end"` | `chunk_position == "last"` | 完整 AI 回复结束 | `DeepAgent >` | 正常 |

**伪代码**:

```python
def __init__(self, ...):
    ...
    self._last_flushed_text: str = ""       # 新增: 最后一次 flush 的文本
    self._last_flush_kind: str | None = None  # 新增: "tool_call" / "message_end"

def _flush_text_buffer(self, *, final: bool = False, flush_kind: str = "message_end") -> None:
    if not final or not self._pending_text.strip():
        return

    self._stop_spinner()
    text = self._pending_text.rstrip()
    self._last_flushed_text = text
    self._last_flush_kind = flush_kind

    prefix_style = f"bold {COLORS['agent']}"
    if flush_kind == "tool_call":
        text_style = "dim"
    else:
        text_style = COLORS["text_primary"]

    self.console.print(f"DeepAgent >", style=prefix_style, end=" ")
    self.console.print(escape(text), style=text_style)
    self._pending_text = ""
```

### 4.3 flush 触发点改造

**触发点 1**: tool call 缓冲完成时（中间文本）

文件: `event_handler.py`, 方法: `_try_display_tool_call()`

```python
def _try_display_tool_call(self, buffer_key, buffer):
    ...
    self._flush_text_buffer(final=True, flush_kind="tool_call")
    ...
```

**触发点 2**: direct `tool_call` 处理时（中间文本）

文件: `event_handler.py`, 方法: `_process_direct_tool_call()`

当 `AIMessage.content_blocks` 中出现 `tool_call`，或消息通过 `message.tool_calls`
直接暴露工具调用时，应先以 `"tool_call"` 来源 flush 缓冲区，再显示工具调用。

```python
def _process_direct_tool_call(self, tool_call):
    ...
    self._flush_text_buffer(final=True, flush_kind="tool_call")
    ...
```

**触发点 3**: AI 消息流结束时（剩余文本视为完整 AI 回复）

文件: `event_handler.py`, 方法: `_process_ai_message_content_blocks()`

```python
def _process_ai_message_content_blocks(self, message):
    ...
    # 先处理 tool_call_chunk / tool_call / direct tool_calls
    ...
    if getattr(message, "chunk_position", None) == "last":
        self._flush_text_buffer(final=True, flush_kind="message_end")
```

**顺序约束**:

1. `content_blocks` 中的 `tool_call_chunk` / `tool_call` 优先处理
2. `message.tool_calls` 仅作为 fallback，避免与 `content_blocks` 重复渲染
3. `message_end` flush 必须在所有工具调用处理之后执行，不能再保持当前“先 flush 再处理 direct tool_calls”的顺序

### 4.4 最终输出去重

**变更对象**: `conversation.py`, `handle_deep_agent_query()` 函数末尾

**规则**:
- 当最后一次 `"message_end"` flush 的文本与 `result["output"]` 一致时，跳过重复打印
- 其他情况保留 `conversation.py` 回退输出，确保最终答案不丢失

**伪代码**:

```python
answer = result.get("output", "No response generated.")
if not event_handler.has_streamed_answer(answer):
    # 回退: messages 流未输出，完整打印
    ctx.console.print(f"[bold blue]DeepAgent >[/] {escape(answer)}")
```

### 4.5 最终答案匹配能力暴露

**变更对象**: `DeepAgentEventHandler` 类

新增只读能力供 `conversation.py` 查询:

```python
def has_streamed_answer(self, answer: str) -> bool:
    """Return whether the final answer has already been rendered by the stream."""
    return (
        self._last_flush_kind == "message_end"
        and self._last_flushed_text.strip() == answer.strip()
    )
```

---

## 5. 视觉效果对照

### 5.1 改造前

```
  Step 21 | 71.8s | model: Calling tools [tavily_search_advanced]
  Step 22 | 71.8s | HumanInTheLoopMiddleware.after_model: None
  Step 23 | 77.5s | tools: Tool 'tavily_search_advanced' completed.
  Step 24 | 77.5s | ExecutionTimeoutMiddleware.before_model: None
  Step 25 | 77.5s | SummarizationMiddleware.before_model: None
  Step 26 | 131.9s | model: 基于我的并行搜索结果，我来为您整理2026年3-4月...  <-- 截断泄露
  Step 27 | 131.9s | HumanInTheLoopMiddleware.after_model: None
  Step 28 | 131.9s | ShellToolMiddleware.after_agent: None
DeepAgent > 基于我的并行搜索结果，我来为您整理2026年3-4月...                 <-- 完整重复
```

### 5.2 改造后

```
  Step 21 | 71.8s | model: Calling tools [tavily_search_advanced]
  Step 22 | 71.8s | HumanInTheLoopMiddleware.after_model: None
  Step 23 | 77.5s | tools: Tool 'tavily_search_advanced' completed.
  Step 24 | 77.5s | ExecutionTimeoutMiddleware.before_model: None
  Step 25 | 77.5s | SummarizationMiddleware.before_model: None
  Step 26 | 131.9s | model: Thinking                                         <-- 功能性描述
  Step 27 | 131.9s | HumanInTheLoopMiddleware.after_model: None
  Step 28 | 131.9s | ShellToolMiddleware.after_agent: None
DeepAgent > 基于我的并行搜索结果，我来为您整理2026年3-4月...(完整内容)       <-- 正常样式
```

### 5.3 包含中间文本的完整交互示例

```
[dim]Deep agent reasoning...[/]

  Step 1  | 0.2s  | model: Thinking
DeepAgent > 让我来深入研究一下2026年3-4月的展会信息            <-- dim 样式（中间）
  Step 2  | 0.5s  | model: Calling tools [web_search]
  Tool: web_search("2026年3-4月 中国 AI展会")
  Step 3  | 5.2s  | tools: Tool 'web_search' completed.
  Step 4  | 5.5s  | model: Thinking
DeepAgent > 我找到了一些信息，让我再搜索一下Web3相关的活动     <-- dim 样式（中间）
  Step 5  | 5.8s  | model: Calling tools [tavily_search_advanced]
  Tool: tavily_search_advanced(query='2026 Web3 conference China')
  Step 6  | 12.3s | tools: Tool 'tavily_search_advanced' completed.
  Step 7  | 45.0s | model: Thinking
DeepAgent > 基于我的并行搜索结果，我来为您整理2026年3-4月     <-- 正常样式（最终）
中国地区AI和Web3相关的展会和活动信息：

# 2026年3-4月中国AI与Web3展会活动汇总
## AI人工智能相关展会
### 1. AWE2026中国家电及消费电子博览会
- 时间: 2026年3月12日-15日
...（完整内容）...

Summary:
  - Reasoning steps: 7
  - Tool calls: 2 (web_search, tavily_search_advanced)
  - Total time: 45.0s
```

---

## 6. 边界情况处理

### 6.1 messages 流无输出（回退场景）

**触发条件**: 模型不支持 `content_blocks`、网络异常导致 messages 流数据丢失、
或模型回复不含 `chunk_position` 属性。

**处理**: `has_streamed_answer(answer)` 返回 `False`，`conversation.py` 正常输出完整的 `DeepAgent >` 行。

### 6.2 `message_end` flush 后仍有下一轮工具调用

**场景**: LLM 先产生一段纯文本消息（`chunk_position == "last"`），下一轮才产生 tool call。

**表现**: 该文本会以正常样式显示，但这并不影响最终答案去重，因为后续是否跳过 fallback
不再依赖简单布尔值，而依赖最后一次 `"message_end"` flush 的文本与最终答案是否一致。

**可接受性**: 这是一个完整的 AI 回复结束，后续新一轮 tool call 会让用户自然理解流程
仍在继续。该误判只影响视觉层，不会导致最终答案丢失或重复。

### 6.3 多次 `"message_end"` flush

**场景**: LLM 在不同轮次产生多段不含 tool_calls 的纯文本。

**表现**: 每段文本都以正常样式 + `DeepAgent >` 前缀显示。最后一段即为最终回答。

**处理**: 仅当最后一段 flush 文本与 `result["output"]` 一致时，conversation.py 才跳过重复输出。
此前各段纯文本不会错误屏蔽最终答案。

### 6.4 空文本 flush

**场景**: `_pending_text` 仅含空白字符。

**处理**: `_flush_text_buffer()` 现有逻辑已包含 `not self._pending_text.strip()` 检查，
空白文本不会触发输出。不需要额外处理。
