# Deep Agent 消息显示问题分析

> **文档定位**: 问题诊断文档，描述现象、根因链路与代码级分析。
>
> **关联文档**:
> [design-proposal.md](./design-proposal.md) -- 方案设计（显示通道分离、样式策略）
> [implementation-plan.md](./implementation-plan.md) -- 实施步骤（修改清单、验证方案）

---

## 术语约定

| 术语 | 含义 | 代码对应 |
|------|------|---------|
| **messages 流** | LangGraph 双流模式中的消息级流，按 chunk 推送 AI 回复片段 | `stream_mode=["messages", ...]` |
| **updates 流** | LangGraph 双流模式中的状态更新流，按节点推送完整状态变更 | `stream_mode=[..., "updates"]` |
| **Step 行** | 终端中以 `Step N \| time \| description` 格式显示的状态追踪行 | `_render_update()` |
| **flush** | 将累积的文本缓冲区内容输出到终端 | `_flush_text_buffer()` |
| **中间文本** | LLM 在工具调用间产生的阶段性说明文本 | 如 "让我来深入研究xx模块" |
| **最终输出** | LLM 完成所有工具调用后产生的最终回答 | 流结束时 `messages[-1]` 的内容 |

---

## 1. 问题现象

### 1.1 现象一: 最终结果的"缩减版"出现在 Step 行中

最终回答的内容被截断后嵌入 Step 行，与状态追踪信息混杂：

```
Step 21 | 71.8s | model: Calling tools [tavily_search_advanced]
Step 22 | 71.8s | HumanInTheLoopMiddleware.after_model: None
Step 23 | 77.5s | tools: Tool 'tavily_search_advanced' completed.
Step 24 | 77.5s | ExecutionTimeoutMiddleware.before_model: None
Step 25 | 77.5s | SummarizationMiddleware.before_model: None
Step 26 | 131.9s | model: 基于我的并行搜索结果，我来为您整理2026年3-4月...   <-- 截断泄露
Step 27 | 131.9s | HumanInTheLoopMiddleware.after_model: None
Step 28 | 131.9s | ShellToolMiddleware.after_agent: None
DeepAgent > 基于我的并行搜索结果，我来为您整理2026年3-4月...              <-- 完整重复
```

**问题**: Step 26 泄露了最终回答的截断版，与随后的 `DeepAgent >` 完整输出构成内容重复。

### 1.2 现象二: 中间"阶段性输出"显示不完整

LLM 在工具调用之间生成的中间文本（如 "让我来深入研究xx模块"、"下面我来整理所有收集到的信息"）
仅以截断形式出现在 Step 行中，且没有明确的来源标记：

```
Step 10 | 45.2s | model: 让我来深入研究xx模块的实现，首先...   <-- 截断到160字符
Step 11 | 45.2s | model: Calling tools [read_file]
```

**问题**: 中间文本缺少完整展示通道，也缺少与最终输出的视觉区分。

### 1.3 期望行为

```
Step 1  | 0.2s  | model: Thinking
DeepAgent > 让我来深入研究xx模块                                 <-- dim 样式，完整中间文本
Step 2  | 0.5s  | model: Calling tools [web_search]
  Tool: web_search("2026年AI展会")
Step 3  | 2.1s  | tools: Tool 'web_search' completed.
Step 4  | 3.0s  | model: Thinking
DeepAgent > 下面我来整理所有收集到的信息                         <-- dim 样式，完整中间文本
Step 5  | 3.5s  | model: Calling tools [tavily_search]
  ...
Step N  | 131.9s | model: Thinking
DeepAgent > 基于我的并行搜索结果，我来为您整理...                <-- 正常样式，最终输出完整展示
...（完整内容）...
```

---

## 2. 架构背景

### 2.1 双流模式架构

系统通过 LangGraph 的 `astream()` 使用双流并行模式获取事件：

```
agent.runtime.astream(input, config, stream_mode=["messages", "updates"])
```

两条流携带不同粒度的信息，由 `DeepAgentEventHandler.handle_event()` 统一分发：

```
streaming event
    |
    +-- stream_mode == "messages"  --> _handle_messages_stream()
    |       |
    |       +-- AIMessageChunk --> _process_ai_message_content_blocks()
    |       |       +-- text block     --> _handle_text_block()      --> 累积到 _pending_text
    |       |       +-- reasoning block --> 跳过（不显示）
    |       |       +-- tool_call_chunk --> _handle_tool_call_chunk() --> 缓冲工具调用
    |       |       +-- chunk_position=="last" --> _flush_text_buffer(final=True)
    |       |
    |       +-- ToolMessage    --> _process_tool_message()
    |
    +-- stream_mode == "updates" --> _handle_updates_stream()
            |
            +-- 遍历 payload 中每个 node
                    +-- _render_update() --> _describe_update() --> Step 行输出
```

### 2.2 AI 消息的三种内容类型

LLM 的 AIMessage 回复中可能包含三种内容：

| 类型 | 说明 | 代码层对应 | 当前处理 |
|------|------|-----------|---------|
| Thinking/CoT | 模型内部推理链（如支持） | `block_type == "reasoning"` | 正确跳过，不显示 |
| 中间步骤说明 | 执行计划、下一步说明等短文本 | 文本后紧跟 tool_calls | 仅在 Step 行中截断显示 |
| 最终输出 | 完成所有工具调用后的最终回答 | 纯文本回复，无后续 tool_calls | Step 行截断 + `DeepAgent >` 重复 |

### 2.3 关键数据流

```
                 messages 流                          updates 流
                    |                                     |
         _pending_text 累积                        _describe_messages()
                    |                                     |
         _flush_text_buffer()                     _render_update()
                    |                                     |
              "Agent:" + 文本                     "Step N | ... | 描述"
            (正常样式，完整)                       (截断到 160 字符)
                    |                                     |
                    +--- 流结束后 ---+                    |
                                     |                    |
                         prepare_stream_result()          |
                         messages[-1] 提取                |
                                     |                    |
                    "DeepAgent > " + 完整文本              |
                                                          |
                    结果: 同一内容最多出现三次
```

---

## 3. 根因分析

### 3.1 问题一根因: `_describe_messages()` 泄露 AI 文本内容到 Step 行

**文件**: `src/application/services/agent/deep/streaming/event_handler.py`
**方法**: `_describe_messages()`

```python
def _describe_messages(self, node: str, messages: Sequence[BaseMessage]) -> str:
    last_message = messages[-1]

    if isinstance(last_message, AIMessage):
        content_snippet = self._truncate(str(last_message.content))  # 截断到 160 字符
        if last_message.tool_calls and self.show_tool_calls:
            tool_names = {call.get("name", "unknown") for call in last_message.tool_calls}
            tools = ", ".join(sorted(tool_names))
            return f"{node}: Calling tools [{tools}]"
        return f"{node}: {content_snippet}"   # <-- 根因: 纯文本 AIMessage 的内容被泄露到 Step 行
```

**逻辑缺陷**: 当 AIMessage 不含 `tool_calls` 时（即纯文本回复），方法将消息内容截断后
直接拼入 Step 描述。这既适用于中间文本也适用于最终回答，导致 AI 生成文本以截断形式
出现在本应只做状态追踪的 Step 行中。

### 3.2 问题二根因: 文本 flush 缺少来源语义

**文件**: `src/application/services/agent/deep/streaming/event_handler.py`
**方法**: `_flush_text_buffer()`

```python
def _flush_text_buffer(self, *, final: bool = False) -> None:
    if not final or not self._pending_text.strip():
        return
    self._stop_spinner()
    if not self._has_responded:
        self.console.print("Agent:", style=f"bold {COLORS['agent']}", markup=False)
        self._has_responded = True
    self.console.print(escape(self._pending_text.rstrip()), style=COLORS["text_primary"])
    self._pending_text = ""
```

**逻辑缺陷**:
1. 中间文本和最终输出使用相同的样式（`COLORS["text_primary"]`），无视觉区分
2. 前缀使用 `"Agent:"`（只打一次），与最终输出的 `"DeepAgent >"` 标记不一致
3. flush 仅接收 `final=True/False`，无法区分“工具调用前的中间文本 flush”和“消息结束时的最终文本 flush”
4. 没有记录最后一次被 flush 的文本内容及其来源，导致 `conversation.py` 无法准确判断“最终答案是否已经被流式输出”

### 3.3 问题三根因: direct `tool_calls` 路径的 flush 顺序错误

**文件**: `src/application/services/agent/deep/streaming/event_handler.py`
**方法**: `_process_ai_message_content_blocks()`, `_process_direct_tool_call()`

```python
def _process_ai_message_content_blocks(self, message: BaseMessage) -> None:
    ...
    if has_content_blocks:
        ...
        if getattr(message, "chunk_position", None) == "last":
            self._flush_text_buffer(final=True)      # <-- 先 flush

    if has_tool_calls:
        for tool_call in message.tool_calls:
            self._process_direct_tool_call(tool_call)   # <-- 后处理 direct tool_calls
```

**逻辑缺陷**:
1. 当消息同时包含文本和 direct `tool_calls` 时，文本会先被 `chunk_position == "last"` 路径按“消息结束”flush
2. 如果这些 `tool_calls` 实际上只是中间步骤，文本就会被误判为最终输出，样式错误且可能触发错误的去重判断
3. 在当前 `.venv` 的 `langchain-core 1.2.2` 中，`AIMessage` / `AIMessageChunk` 既可能通过 `content_blocks` 提供 `tool_call_chunk`，也可能提供 `tool_call` 与 `message.tool_calls`，仅靠现有顺序无法稳定覆盖所有形态

### 3.4 问题四根因: 最终输出重复

**文件**: `src/application/services/agent/deep/streaming/conversation.py`
**位置**: `handle_deep_agent_query()` 流结束后

```python
answer = result.get("output", "No response generated.")
ctx.console.print(f"[bold blue]DeepAgent >[/] {escape(answer)}")   # 无条件完整输出
```

**逻辑缺陷**:
1. 最终输出无条件打印完整内容。当 messages 流已经通过 `_flush_text_buffer()` 完整输出了最终文本时，此处再次输出构成重复
2. 即使引入“是否流式输出过文本”的简单布尔状态，也仍然不足以做准确去重
3. 如果 messages 流只输出过中间文本，而最终答案未成功 flush，简单布尔判断会把真正的最终答案误跳过

### 3.5 根因关系图

```
_describe_messages() 泄露内容到 Step 行        (问题一根因)
        |
        +--- 同一消息同时在 updates 流和 messages 流到达
        |
        v
_flush_text_buffer() 无法区分 flush 来源        (问题二根因)
        |
        +--- 前缀不一致 ("Agent:" vs "DeepAgent >")
        +--- 无中间/最终样式区分
        +--- 无最后一次 flush 文本/来源追踪
        |
        v
_process_ai_message_content_blocks() 顺序错误    (问题三根因)
        |
        +--- 先按 message_end flush
        +--- 后处理 direct tool_calls
        +--- 中间文本可能被误判为最终输出
        |
        v
conversation.py 无条件完整输出最终回答          (问题四根因)
        |
        +--- 缺少“最终答案是否已被流式输出”的精确判断
        |
        v
结果: 最终回答最多出现三次（Step 截断 + 流式完整 + DeepAgent 完整）
```

---

## 4. 影响范围

### 4.1 受影响的文件

| 文件 | 架构层 | 影响 |
|------|--------|------|
| `src/application/services/agent/deep/streaming/event_handler.py` | 事件处理 | Step 描述生成、文本 flush 逻辑 |
| `src/application/services/agent/deep/streaming/conversation.py` | 会话编排 | 最终输出显示逻辑 |

### 4.2 不受影响的部分

- 消息持久化逻辑（`DeepAgentCheckpointer`）: 持久化基于 runtime state，与显示无关
- HITL 中断/恢复流程: 中断处理在流式循环之外，显示改动不影响其逻辑
- 工具调用显示（`_render_tool_call`）: 工具调用的显示逻辑独立于 AI 文本显示
- `base_deep_agent.py` 中的 `prepare_stream_result()`: 数据提取逻辑不变，仅消费端行为调整
