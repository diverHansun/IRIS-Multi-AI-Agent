# ToolMessage 持久化：问题分析

## 1. 当前架构概览

### 1.1 双 Checkpointer 架构（Deep 模式）

```
用户输入
   |
   v
enhance_runtime_input() -- 从 SessionStorage 加载历史，追加新查询
   |
   v
MemorySaver (运行时)    -- 维护完整执行状态，支持 HITL 中断/恢复
   |                       包含所有消息类型：Human, AI, Tool, System
   v
astream() 流式执行       -- agent 循环：AI -> Tool -> AI -> Tool -> ...
   |
   v
persist_from_runtime()  -- 从 MemorySaver 提取消息，过滤后写入 SessionStorage
   |
   v
SessionStorage (持久化)  -- JSON 文件，仅保存 HumanMessage + AIMessage

注意：当前 astream() 使用 durability="exit"，意味着 MemorySaver 仅在 graph 退出时
才收到 put()/put_writes() 调用。执行过程中 MemorySaver 无中间状态。
```

### 1.2 单 Checkpointer 架构（Basic 模式）

```
用户输入
   |
   v
BasicAgentCheckpointer  -- 实现 BaseCheckpointSaver 接口
   |                       get_tuple(): 从 SessionStorage 加载
   |                       put(): 每步执行后保存到 SessionStorage
   v
SessionStorage (持久化)  -- 与 Deep 模式共用同一存储层
```

### 1.3 消息类型与当前处理

| 消息类型       | 运行时存在 | 持久化保存 | 序列化字段                |
|---------------|-----------|-----------|--------------------------|
| HumanMessage  | 是        | 是        | type, content, timestamp |
| AIMessage     | 是        | 是        | type, content, timestamp |
| ToolMessage   | 是        | **否**    | --                       |
| SystemMessage | 是        | 否        | --                       |

关键缺陷：AIMessage 的 `tool_calls` 字段在序列化时被静默丢弃。

---

## 2. 问题清单

### 问题 P1：ToolMessage 未持久化

**位置：** `_filter_messages()` in `basic_agent_checkpointer.py:224-227` 和 `deep_agent_checkpointer.py:258-274`

**现状：**

```python
def _filter_messages(self, messages):
    flattened = self._flatten_messages(messages)
    return [m for m in flattened if isinstance(m, (HumanMessage, AIMessage))]
```

ToolMessage 被显式过滤。Session 重新加载后，LLM 不知道之前用了什么 tool、结果是什么，上下文断裂。

**影响：**
- LLM 无法基于历史 tool 调用结果继续推理
- 多轮 tool 使用场景中，LLM 重复调用已经执行过的 tool
- 对话连贯性下降

---

### 问题 P2：AIMessage.tool_calls 序列化缺失

**位置：** `session_storage.py:59-65`

**现状：**

```python
def _message_to_dict(self, message):
    return {
        "type": message.__class__.__name__,
        "content": message.content,            # 仅保存 content
        "timestamp": datetime.now().isoformat()
    }
```

AIMessage 的 `tool_calls` 字段未被序列化。反序列化时 `AIMessage(content=content)` 创建的对象 `tool_calls=[]`。

**风险：** 如果仅修复 P1（保存 ToolMessage）而不修复 P2，reload 后 AIMessage 没有 tool_calls 但存在对应 ToolMessage，虽然不会触发 LangGraph 验证错误（验证方向是 tool_calls -> ToolMessage），但 LLM 无法理解 tool_call 与 tool_result 的对应关系，上下文语义断裂。

P1 和 P2 必须同时修复。

---

### 问题 P3：LangGraph 消息序列验证约束

**位置：** `.venv/.../langgraph/prebuilt/chat_agent_executor.py`

**约束：** `_validate_chat_history()` 在每次 LLM 调用前验证：

```python
# 简化表示
for ai_msg in messages:
    for tool_call in ai_msg.tool_calls:
        if tool_call["id"] not in tool_message_ids:
            raise ValueError("INVALID_CHAT_HISTORY")
```

**含义：** 持久化后的消息序列必须满足以下不变量：

> 对于每个 AIMessage 中的每个 tool_call，必须存在一个 tool_call_id 匹配的 ToolMessage。

违反此不变量 = agent 启动时崩溃。这个约束贯穿后续所有设计决策。

---

### 问题 P4：消息截断破坏序列完整性

**位置：** `_trim_messages()` in 两个 checkpointer 中

**现状：**

```python
def _trim_messages(self, messages):
    if self.max_messages and len(messages) > self.max_messages:
        return messages[-self.max_messages:]
    return messages
```

简单取最后 N 条消息。加入 ToolMessage 后，一个完整的 agent turn 的消息结构为：

```
HumanMessage("查找文件")
AIMessage(tool_calls=[{name: "shell", id: "tc_001"}])   <-- 如果截断点在这里
ToolMessage(tool_call_id="tc_001", content="file.txt")   <-- 这条被保留
AIMessage("找到了 file.txt")
```

如果截断点落在 AIMessage(tool_calls) 和 ToolMessage 之间：
- 丢失 AIMessage(tool_calls) → ToolMessage 成为孤儿 → LLM 无法理解上下文
- 保留 AIMessage(tool_calls) 但丢失 ToolMessage → 违反 P3 的不变量 → crash

**需要：** 感知消息边界的截断策略，确保 AIMessage(tool_calls) 和对应 ToolMessage 组作为不可分割单元。

---

### 问题 P5：enhance_runtime_input 的 max_history 语义变化

**位置：** `deep_agent_checkpointer.py:49-65`

**现状：** `max_history=10` 取最后 10 条消息，当前全是 Human/AI，约等于 5 轮对话。

**变化后：** 加入 ToolMessage，一个 agent turn 可能包含：

```
HumanMessage                         # 1 条
AIMessage(tool_calls=[tc1, tc2])     # 1 条
ToolMessage(tc1)                     # 1 条
ToolMessage(tc2)                     # 1 条
AIMessage("final answer")            # 1 条
---
共 5 条消息 = 1 个完整 turn
```

`max_history=10` 只能恢复约 2 个 turn 的上下文，远少于之前的 5 轮。

**需要：** 将计数单位从"消息数"改为"turn 数"，或显著增大 max_history 值。

---

### 问题 P6：BasicAgentCheckpointer 去重策略与 ToolMessage 不兼容

**位置：** `basic_agent_checkpointer.py:229-239`

**现状：**

```python
def _deduplicate_messages(self, messages):
    seen = set()
    deduped = []
    for msg in messages:
        key = (type(msg).__name__, msg.content)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(msg)
    return deduped
```

使用 `(type, content)` 作为去重 key。问题：
- 多个不同 tool_call 可能返回相同内容的 ToolMessage（例如多次 shell 调用返回 "OK"）
- 全局去重会错误地删除有效的 ToolMessage → 破坏 P3 的不变量

**需要：** 将 `tool_call_id` 纳入去重 key，或对 ToolMessage 跳过去重。

---

### 问题 P7：MessageFilter 同步更新

**位置：** `message_filter.py:132-183`

`filter_message_history()` 的过滤逻辑：

```python
if self.is_system_notification(message):  # SystemMessage 或 ToolMessage → 跳过
    i += 1
    continue
```

将 ToolMessage 归类为"系统通知"并跳过。如果项目中其他位置使用 `MessageFilter` 处理消息历史，需要同步更新。

**需要：** 检查 `MessageFilter` 的所有调用点，确认影响范围。

---

### 问题 P8：Deep 模式缺少中间崩溃保护

**位置：** `conversation.py` 的 streaming loop（第 208-351 行）

**现状持久化触发点：**

| 触发条件           | 代码位置    | 覆盖场景       |
|-------------------|------------|---------------|
| 正常完成           | 第 403 行  | agent 完成所有工作 |
| Ctrl+C 中断       | 第 361 行  | 用户主动中断     |
| Step Timeout      | 第 248 行  | 单步超时        |
| Execution Timeout | 第 287 行  | 总执行时间超限   |

**未覆盖场景：**
- 进程被 kill（SIGKILL）
- Python 异常导致崩溃
- 系统断电/蓝屏
- OOM killer

在这些场景下，agent 可能已经执行了多个 tool 调用（每个调用可能产生不可逆副作用），但所有执行记录丢失。

**需要：** 在 streaming loop 中增加 per-step 持久化，确保每个 tool 执行完成后立即将当前状态写入磁盘。最坏情况下只丢失最后一个未完成的 step。

---

### 问题 P9：durability="exit" 阻断 mid-stream 持久化

**位置：** `conversation.py:219` — `durability="exit"` 参数

**背景：**

LangGraph 的 `durability` 参数控制 checkpointer 的写入时机：
- `"sync"`：每步同步写入 checkpointer
- `"async"`：每步异步写入 checkpointer（默认值）
- `"exit"`：仅在 graph 退出时写入 checkpointer

**当前状态：**

Deep 模式的 graph 编译时传入的 checkpointer 是 **MemorySaver**（`agent.runtime_checkpointer`），不是 DeepAgentCheckpointer。见 `factories/base.py:173`：

```python
runtime = create_deep_agent_runtime(
    ...
    checkpointer=agent.runtime_checkpointer,  # ← MemorySaver
    ...
)
```

`durability="exit"` 导致 LangGraph 在执行过程中**不调用** MemorySaver 的 `put()` / `put_writes()`。因此：
- MemorySaver 在 mid-stream 时没有中间状态
- `persist_from_runtime()` 调用 `runtime_checkpointer.get_tuple(config)` 读到的是**上次执行结束时的旧状态**
- Phase D 的 per-step 持久化**完全失效**

**影响：** P8 的解决方案（per-step persist）依赖 MemorySaver 有中间状态。durability="exit" 是 P8 的前置阻塞问题。

**需要：** 将 `durability="exit"` 改为 `durability="async"`（LangGraph 默认值）。改为 "async" 后：
- MemorySaver 每步异步更新（纯内存 dict 操作，几乎零开销）
- `persist_from_runtime()` 随时可读到最新状态
- 对 HITL 无影响（HITL 依赖 `__interrupt__` 机制，与 durability 模式无关）
- 对性能无影响（MemorySaver 是内存操作，"async" 模式下不阻塞主执行流）

---

### 问题 P10：persist_from_runtime 中 existing 无用加载

**位置：** `deep_agent_checkpointer.py:110`

**现状：**

```python
existing = self.storage.load_session(session_id) or []
logger.debug("[PERSIST] Existing session messages: %d", len(existing))
```

`existing` 被加载但从未参与后续逻辑。当前是 "direct replacement" 策略（filtered → dedup → trim → save），`existing` 完全冗余。这是一次无意义的磁盘 I/O，在 per-step 持久化场景下会被放大（每步都做无用读取）。

**需要：** 移除无用加载和对应的 debug log。如未来需要 merge 策略，在那时重新引入。

---

## 3. 问题依赖关系

```
P1 (ToolMessage 未持久化)
 |
 +-- P2 (AIMessage.tool_calls 未序列化) -- 必须同时修复
 |
 +-- P3 (LangGraph 序列验证约束) -- 贯穿所有设计决策
 |    |
 |    +-- P4 (截断破坏序列) -- 受 P3 约束
 |    |
 |    +-- P6 (去重破坏序列) -- 受 P3 约束
 |
 +-- P5 (max_history 语义变化) -- P1 的直接后果
 |
 +-- P7 (MessageFilter 同步) -- P1 的间接影响

P8 (中间崩溃保护)
 |
 +-- P9 (durability="exit" 阻断 mid-stream) -- P8 的前置阻塞
 |
 +-- P10 (persist_from_runtime 无用加载) -- per-step 场景下放大 I/O 浪费
```

## 4. 影响范围

| 文件 | 变更类型 | 涉及问题 |
|-----|---------|---------|
| `session_storage.py` | 序列化/反序列化扩展 | P1, P2 |
| `deep_agent_checkpointer.py` | filter, dedup, trim, enhance, 移除无用加载 | P1, P4, P5, P6, P10 |
| `basic_agent_checkpointer.py` | filter, dedup, trim | P1, P4, P6 |
| `conversation.py` (deep) | durability 改为 "async"；streaming loop write-through | P8, P9 |
| `message_filter.py` | ToolMessage 分类更新 | P7 |
| `event_handler.py` (可能) | step 完成信号 | P8 |
