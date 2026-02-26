# ToolMessage 持久化：设计方案

本文档描述 Approach A（序列化扩展 + 截断）+ Approach X（streaming loop per-step 持久化）的详细设计。

## 1. 设计原则

- **序列不变量优先**：所有变更必须保证持久化后的消息序列满足 LangGraph 的 `_validate_chat_history()` 验证
- **向后兼容**：旧 session 文件（无 tool_calls/ToolMessage）可正常加载，无需迁移
- **双 Checkpointer 架构不变**：MemorySaver 管理运行时状态，SessionStorage 管理持久化
- **YAGNI**：ToolMessage 内容截断用于 LLM 上下文恢复，不做审计级全量保留

---

## 2. SessionStorage 序列化扩展（解决 P1, P2）

### 2.1 _message_to_dict 扩展

当前签名：`_message_to_dict(self, message: BaseMessage) -> Dict[str, Any]`

变更后序列化格式：

**HumanMessage**（不变）：
```json
{
  "type": "HumanMessage",
  "content": "查找所有 Python 文件",
  "timestamp": "2026-02-26T10:30:00"
}
```

**AIMessage**（新增 tool_calls）：
```json
{
  "type": "AIMessage",
  "content": "我来帮你查找...",
  "tool_calls": [
    {
      "name": "shell",
      "args": {"command": "find . -name '*.py'"},
      "id": "call_abc123"
    }
  ],
  "timestamp": "2026-02-26T10:30:01"
}
```

当 `tool_calls` 为空时，不写入该字段（向后兼容）。

**ToolMessage**（新增）：
```json
{
  "type": "ToolMessage",
  "content": "file1.py\nfile2.py\nfile3.py...",
  "tool_call_id": "call_abc123",
  "name": "shell",
  "timestamp": "2026-02-26T10:30:02"
}
```

### 2.2 ToolMessage 内容截断

引入配置常量：

```python
MAX_TOOL_CONTENT_LENGTH = 500  # 字符数
TOOL_CONTENT_TRUNCATION_SUFFIX = "\n... [truncated, {original_length} chars total]"
```

截断逻辑在 `_message_to_dict` 中执行：

```python
if isinstance(message, ToolMessage):
    content = message.content
    if isinstance(content, str) and len(content) > MAX_TOOL_CONTENT_LENGTH:
        content = content[:MAX_TOOL_CONTENT_LENGTH] + \
            TOOL_CONTENT_TRUNCATION_SUFFIX.format(original_length=len(message.content))
    return {
        "type": "ToolMessage",
        "content": content,
        "tool_call_id": message.tool_call_id,
        "name": getattr(message, "name", ""),
        "timestamp": datetime.now().isoformat(),
    }
```

截断发生在序列化时（写入磁盘时），不影响运行时 MemorySaver 中的完整 ToolMessage。

**决策：** `MAX_TOOL_CONTENT_LENGTH` 先作为硬编码常量（500 字符）。如果后续发现不同 tool 输出差异过大需要按 tool 类型调整，再提升为配置项（接入点：`SessionStorage` 构造参数或 config.json）。

### 2.3 _dict_to_message 扩展

```python
def _dict_to_message(self, msg_dict):
    msg_type = msg_dict.get("type", "HumanMessage")
    content = msg_dict.get("content", "")

    if msg_type == "HumanMessage":
        return HumanMessage(content=content)

    elif msg_type == "AIMessage":
        tool_calls = msg_dict.get("tool_calls", [])
        msg = AIMessage(content=content, tool_calls=tool_calls)
        return msg

    elif msg_type == "ToolMessage":
        return ToolMessage(
            content=content,
            tool_call_id=msg_dict.get("tool_call_id", ""),
            name=msg_dict.get("name", ""),
        )

    elif msg_type == "SystemMessage":
        # 向后兼容：旧数据中的 SystemMessage 转为 HumanMessage
        logger.warning("Found SystemMessage in persisted data, converting to HumanMessage")
        return HumanMessage(content=content)

    else:
        logger.debug("Unknown message type '%s', converting to HumanMessage", msg_type)
        return HumanMessage(content=content)
```

### 2.4 向后兼容性

旧 session 文件中的 AIMessage 没有 `tool_calls` 字段：
- `msg_dict.get("tool_calls", [])` 返回空列表
- `AIMessage(content=..., tool_calls=[])` → 合法对象，不触发验证错误

旧 session 文件中没有 ToolMessage：
- 加载后消息列表中无 ToolMessage → AIMessage.tool_calls 为空 → 序列合法

无需数据迁移。

---

## 3. Checkpointer _filter_messages 扩展（解决 P1）

### 3.1 统一变更

两个 checkpointer 的 `_filter_messages` 统一修改为：

```python
def _filter_messages(self, messages):
    flattened = self._flatten_messages(messages)
    return [m for m in flattened if isinstance(m, (HumanMessage, AIMessage, ToolMessage))]
```

仅增加 `ToolMessage` 到类型元组中。SystemMessage 继续排除。

### 3.2 导入变更

两个 checkpointer 文件需要在导入中增加 `ToolMessage`：

```python
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
```

---

## 4. 序列安全的截断策略（解决 P4）

### 4.1 问题定义

消息序列中存在"不可分割组"（atomic group）：

```
组边界 ─┐
        │  AIMessage(tool_calls=[tc1, tc2])
        │  ToolMessage(tool_call_id=tc1)
        │  ToolMessage(tool_call_id=tc2)
组边界 ─┘
        │  AIMessage(content="final answer", tool_calls=[])  ← 独立消息
组边界 ─┘
```

一个 AIMessage 和它的所有对应 ToolMessage 构成一个原子组。截断必须以原子组为单位。

### 4.2 算法

```python
def _trim_messages(self, messages):
    if not self.max_messages or len(messages) <= self.max_messages:
        return messages

    # 从尾部向前扫描，识别原子组边界
    # 一个原子组 = AIMessage(tool_calls非空) + 对应的 ToolMessages
    # 独立消息（HumanMessage, AIMessage(tool_calls=[]), 孤立 ToolMessage）各自为一组

    groups = self._split_into_atomic_groups(messages)

    # 从最新的组开始，累计消息数，直到超过 max_messages
    result = []
    for group in reversed(groups):
        if len(result) + len(group) > self.max_messages and result:
            break
        result = group + result

    return result
```

`_split_into_atomic_groups` 的逻辑：

```
扫描消息列表，维护当前 pending_tool_call_ids 集合：
1. 遇到 AIMessage(tool_calls 非空)：
   - 如果有 pending 集合未清空，先关闭当前组
   - 开始新组，记录 tool_call_ids
2. 遇到 ToolMessage：
   - 如果 tool_call_id 在 pending 集合中，加入当前组，从 pending 移除
   - 如果 pending 集合清空，关闭当前组
3. 遇到 HumanMessage 或 AIMessage(tool_calls=[])：
   - 关闭当前组（如果有），开始并立即关闭新的单消息组
```

### 4.3 边界情况

- 截断后第一条消息是 ToolMessage（孤儿）→ 作为独立组保留，LLM 能看到 tool 结果但缺少调用上下文。这比丢失更好，且不违反 LangGraph 验证（验证方向是 tool_calls → ToolMessage，不检查 ToolMessage → AIMessage）。
- 截断后消息数可能略超过 max_messages（因为不能拆分原子组）→ 可接受，这是上限而非精确值。

---

## 5. 去重策略修正（解决 P6）

### 5.1 BasicAgentCheckpointer 修正

```python
def _deduplicate_messages(self, messages):
    seen = set()
    deduped = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            # ToolMessage 用 tool_call_id 去重，不用 content
            key = ("ToolMessage", getattr(msg, "tool_call_id", id(msg)))
        else:
            key = (type(msg).__name__, msg.content if hasattr(msg, "content") else "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(msg)
    return deduped
```

### 5.2 DeepAgentCheckpointer 修正

Deep 模式当前使用连续去重（仅去重相邻重复）。ToolMessage 的连续重复极少发生，但为安全起见也加入 tool_call_id 判断：

```python
def _deduplicate_messages(self, messages):
    if not messages:
        return []
    deduped = [messages[0]]
    for msg in messages[1:]:
        prev = deduped[-1]
        # ToolMessage: 用 tool_call_id 判断是否重复
        if isinstance(msg, ToolMessage) and isinstance(prev, ToolMessage):
            if getattr(msg, "tool_call_id", None) == getattr(prev, "tool_call_id", None):
                continue
        elif type(msg).__name__ == type(prev).__name__ and msg.content == prev.content:
            continue
        deduped.append(msg)
    return deduped
```

---

## 6. enhance_runtime_input 改为 turn 计数（解决 P5）

### 6.1 语义变更

将 `max_history` 参数的语义从"最大消息数"改为"最大 turn 数"。一个 turn 定义为：

```
HumanMessage + [AIMessage(tool_calls) + ToolMessages]* + AIMessage(final)
```

即从 HumanMessage 开始，到下一个 HumanMessage 之前的所有消息。

### 6.2 实现

```python
def enhance_runtime_input(self, session_id, user_query, max_history=10):
    messages = []
    try:
        stored = self.storage.load_session(session_id)
        if stored:
            messages = self._extract_recent_turns(stored, max_turns=max_history)
    except Exception as exc:
        logger.warning("Failed to load history: %s", exc)

    messages.append(HumanMessage(content=user_query))
    return {"messages": messages}

def _extract_recent_turns(self, messages, max_turns):
    """从消息列表末尾提取最近 N 个 turn。"""
    # 从后向前扫描，遇到 HumanMessage 计为一个 turn 的开始
    turn_starts = []
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            turn_starts.append(i)

    if not turn_starts:
        return messages  # 没有 HumanMessage，返回全部

    # 取最后 max_turns 个 turn 的起始位置
    start_idx = turn_starts[-max_turns] if len(turn_starts) >= max_turns else turn_starts[0]
    return messages[start_idx:]
```

### 6.3 默认值

`max_history=10` 的语义变为"最近 10 个 turn"。每个 turn 平均 3-5 条消息（Human + AI + 0-N Tool），实际加载 30-50 条消息。

**决策：保持默认值 10 turn。** 理由：
- 10 turn × 3-5 msg/turn = 30-50 条消息，与 `max_messages=100` 的 trim 阈值相比有充足空间
- 10 turn 提供足够上下文让 LLM 理解对话走向
- 降到 5 turn 会导致 LLM 在复杂多步任务中丢失早期决策上下文
- 如果 token 预算成为问题（加入 ToolMessage 后每条消息更大），可之后下调

---

## 7. MessageFilter 同步更新（解决 P7）

### 7.1 is_system_notification 修正

当前：

```python
def is_system_notification(self, message):
    return isinstance(message, (SystemMessage, ToolMessage))
```

修改为：

```python
def is_system_notification(self, message):
    return isinstance(message, SystemMessage)
```

ToolMessage 不再被视为系统通知。

### 7.2 filter_message_history 修正

当前逻辑跳过 ToolMessage（因为 `is_system_notification` 返回 True）。修改后 ToolMessage 不会被跳过，但也需要确保 filter 不会破坏消息序列。

考虑到 `filter_message_history` 的主要用途是过滤系统命令和通知，ToolMessage 应该被原样保留：

```python
while i < len(messages):
    message = messages[i]

    # 跳过系统通知（仅 SystemMessage）
    if self.is_system_notification(message):
        i += 1
        continue

    # ToolMessage：原样保留
    if isinstance(message, ToolMessage):
        filtered_messages.append(message)
        i += 1
        continue

    # 后续逻辑不变...
```

### 7.3 调用点影响评估

需要在实施前检查 `MessageFilter` 的所有调用点，确认修改不会产生意外副作用。

---

## 8. Deep 模式 Per-Step 持久化（解决 P8, P9, P10）

### 8.1 前置条件：durability 变更（解决 P9）

当前 `conversation.py:219` 使用 `durability="exit"`，导致 MemorySaver 在执行过程中没有中间状态。这是 per-step 持久化的前置阻塞。

**变更：** 移除 `durability="exit"` 参数（使用 LangGraph 默认值 `"async"`）。

```python
# 变更前
async for event in agent.runtime.astream(
    pending_input,
    config=runtime_config,
    stream_mode=["messages", "updates"],
    subgraphs=True,
    durability="exit",       # ← 移除此行
):

# 变更后
async for event in agent.runtime.astream(
    pending_input,
    config=runtime_config,
    stream_mode=["messages", "updates"],
    subgraphs=True,
    # durability 使用默认值 "async"
    # MemorySaver 每步异步更新，支持 mid-stream persist
):
```

**影响分析：**
- MemorySaver 每步异步更新（纯内存 dict 操作，几乎零开销）
- 对 HITL 无影响（HITL 依赖 `__interrupt__` 机制，与 durability 无关）
- 对性能无影响（"async" 模式不阻塞主执行流）
- `persist_from_runtime()` 随时可读到最新状态

### 8.2 前置条件：移除 persist_from_runtime 无用加载（解决 P10）

`deep_agent_checkpointer.py:110` 的 `existing = self.storage.load_session(session_id) or []` 加载了但从未使用（"direct replacement" 策略）。在 per-step 场景下，每步都做无用磁盘读取。

**变更：** 移除 `existing` 加载和对应 debug log。

### 8.3 设计目标

在 agent 执行过程中，每完成一个 tool 调用周期后立即将当前状态写入磁盘。最坏情况下（进程被 kill），只丢失最后一个未完成的 step。

### 8.4 触发时机

streaming loop 中，`astream()` 以 `stream_mode=["messages", "updates"]` 产生事件。当收到 "tools" node 的 `updates` 事件时，表示 tool 执行完成，此时 MemorySaver 已包含完整的 AI(tool_calls) + ToolMessage(result)。

在 `event_handler.handle_event()` 的返回值中增加 `step_completed: bool` 标志：

```python
@dataclass
class EventHandlerResult:
    interrupts: Optional[Tuple[Interrupt, ...]] = None
    step_completed: bool = False  # 新增
```

当 event_handler 检测到 tools node 的 updates 事件时，设置 `step_completed = True`。

### 8.5 conversation.py 集成

```python
async for event in agent.runtime.astream(pending_input, config=runtime_config, ...):
    result = event_handler.handle_event(event)

    if result.interrupts:
        captured_interrupts = result.interrupts

    # Per-step 持久化：tool 执行完成后立即写入磁盘
    if result.step_completed:
        try:
            deep_checkpointer.persist_from_runtime(
                session_id, runtime_checkpointer, runtime_config, agent_state=None
            )
        except Exception as exc:
            logger.warning("Per-step persistence failed: %s", exc)
        # 不 break，继续执行

    if deadline is not None and time.perf_counter() > deadline:
        timed_out = True
        break
```

### 8.6 I/O 频率分析

典型 agent 任务中 tool 调用次数：
- 简单查询：0-2 次 tool 调用 → 0-2 次额外 I/O
- 中等任务：3-10 次 → 3-10 次额外 I/O
- 复杂任务：10-30 次 → 10-30 次额外 I/O

每次 `persist_from_runtime()` 涉及：
1. 从 MemorySaver 读取 checkpoint（内存操作）
2. 过滤、去重、截断（CPU 操作）
3. 写入 JSON 文件（磁盘 I/O）
4. 更新 sessions_index.json（磁盘 I/O）

单次写入耗时估计 < 10ms（本地磁盘，小文件），对 agent 总执行时间（通常数秒到数分钟）影响可忽略。

### 8.7 Basic 模式

Basic 模式通过 LangGraph 的 `checkpointer.put()` 机制已经实现 per-step 持久化，无需额外处理。

---

## 9. 变更汇总

| 文件 | 变更内容 | 解决问题 |
|-----|---------|---------|
| `session_storage.py` | `_message_to_dict` 支持 AIMessage.tool_calls 和 ToolMessage；`_dict_to_message` 反序列化扩展；引入 `MAX_TOOL_CONTENT_LENGTH` 常量（硬编码，后续按需配置化） | P1, P2 |
| `deep_agent_checkpointer.py` | `_filter_messages` 增加 ToolMessage；`_trim_messages` 改为原子组截断；`_deduplicate_messages` 增加 tool_call_id 判断；`enhance_runtime_input` 改为 turn 计数（默认 10 turn）；`_extract_recent_turns` 新方法；`persist_from_runtime` 移除无用 existing 加载 | P1, P4, P5, P6, P10 |
| `basic_agent_checkpointer.py` | `_filter_messages` 增加 ToolMessage；`_trim_messages` 改为原子组截断；`_deduplicate_messages` 增加 tool_call_id 判断 | P1, P4, P6 |
| `conversation.py` (deep streaming) | 移除 `durability="exit"`（使用默认 "async"）；streaming loop 中检测 step_completed 后调用 persist | P8, P9 |
| `event_handler.py` | `EventHandlerResult` 增加 `step_completed` 字段；检测 tools node updates 事件 | P8 |
| `message_filter.py` | `is_system_notification` 排除 ToolMessage；`filter_message_history` 保留 ToolMessage | P7 |
