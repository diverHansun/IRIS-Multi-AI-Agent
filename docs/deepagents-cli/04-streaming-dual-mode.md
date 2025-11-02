# 流式处理双模式支持实施文档

## deepagents-cli官方代码的优点

### 1. 双模式流式处理

官方使用 `stream_mode=["messages", "updates"]` 双模式设计：

- **messages模式**：处理agent的文本响应和工具调用内容
- **updates模式**：处理系统元数据，如中断、todo更新、状态变更
- **职责分离**：内容流和元数据流分离，避免混在一起难以处理

### 2. 工具调用分块处理

官方正确处理流式工具调用的分块数据：

- **content_blocks解析**：从 `AIMessage` 的 `content_blocks` 中提取工具调用块
- **分块缓冲**：使用 `tool_call_buffers` 缓冲不完整的工具调用
- **JSON解析等待**：等待完整的JSON数据后再解析和显示
- **去重机制**：使用 `displayed_tool_ids` 避免重复显示同一个工具调用

### 3. 内容块类型处理

官方区分不同类型的content blocks：

- **text块**：累积后统一渲染为Markdown
- **reasoning块**：推理步骤（可选显示）
- **tool_call_chunk块**：工具调用的流式分块

### 4. 状态同步机制

正确处理流式状态同步：

- **摘要模式检测**：检测来自 `SummarizationMiddleware` 的消息
- **文本缓冲刷新**：在适当时机刷新累积的文本内容
- **Spinner控制**：根据是否有内容更新控制"思考中"提示的显示

## 我们现有代码的优点和不足

### 优点

1. **流式处理已实现**：`handle_deep_agent_query` 中已使用 `astream` 处理事件
2. **事件处理框架**：`DeepAgentEventHandler` 可以处理各种事件类型
3. **中断处理支持**：已实现HITL中断的处理和恢复

### 不足

1. **单模式流式处理**：当前使用 `stream_mode="updates"` 单模式，所有内容混在一起
2. **缺少content_blocks解析**：没有处理 `AIMessage` 的 `content_blocks` 结构
3. **工具调用显示不完整**：流式工具调用可能显示不完整或重复
4. **文本缓冲缺失**：没有缓冲部分文本内容，导致显示不流畅

## 实施方案

### 实施步骤

#### 第一步：修改流式处理配置

**文件路径**：`src/application/services/agent/deep/streaming/conversation.py`

**修改 `handle_deep_agent_query` 函数**：
- 将 `stream_mode="updates"` 改为 `stream_mode=["messages", "updates"]`
- 确保agent runtime支持双模式流式处理

**代码修改**：
```python
async for event in agent.runtime.astream(
    pending_input,
    config=runtime_config,
    stream_mode=["messages", "updates"],  # 双模式
):
```

#### 第二步：增强Event Handler处理双模式

**文件路径**：`src/application/services/agent/deep/streaming/event_handler.py`

**修改 `handle_event` 方法**：
- 识别chunk的结构：`(namespace, stream_mode, data)`
- 根据 `stream_mode` 分发处理：
  - `"messages"`：处理内容块和工具调用
  - `"updates"`：处理中断和todo更新

**处理逻辑**：
```python
if isinstance(chunk, tuple) and len(chunk) == 3:
    namespace, current_stream_mode, data = chunk
    if current_stream_mode == "messages":
        # 处理消息内容
    elif current_stream_mode == "updates":
        # 处理元数据更新
```

#### 第三步：实现content_blocks解析

**文件路径**：`src/application/services/agent/deep/streaming/event_handler.py`

**新增方法**：`_process_message_content_blocks()`

**功能**：
- 遍历 `AIMessage.content_blocks`
- 识别不同类型的块：
  - `text`：累积到文本缓冲区
  - `reasoning`：可选显示推理步骤
  - `tool_call_chunk`：处理工具调用分块

#### 第四步：实现工具调用分块缓冲

**文件路径**：`src/application/services/agent/deep/streaming/event_handler.py`

**新增属性**：
- `tool_call_buffers`：字典，键为工具调用ID或index
- `displayed_tool_ids`：已显示的工具调用ID集合

**缓冲逻辑**：
- 使用 `tool_call_chunk` 的 `index` 或 `id` 作为缓冲键
- 累积不完整的JSON字符串
- 当JSON完整后解析并显示
- 使用ID去重，避免重复显示

**代码结构**：
```python
def _buffer_tool_call_chunk(self, block: dict):
    """缓冲工具调用分块"""
    chunk_id = block.get("id") or block.get("index")
    buffer = self.tool_call_buffers.setdefault(chunk_id, {})
    # 累积JSON字符串
    # 尝试解析，成功后显示并清理缓冲
```

#### 第五步：实现文本缓冲和刷新

**文件路径**：`src/application/services/agent/deep/streaming/event_handler.py`

**新增属性**：
- `pending_text`：累积的文本内容
- `summary_buffer`：摘要消息缓冲区
- `summary_mode`：是否处于摘要模式

**刷新逻辑**：
- 检测是否为摘要消息（`SummarizationMiddleware` 的输出）
- 文本块累积到缓冲区
- 在适当时机（消息结束、工具调用前）刷新并渲染

#### 第六步：增强UI渲染时机

**文件路径**：`src/application/services/agent/deep/streaming/event_handler.py`

**渲染优化**：
- 在文本块累积到一定长度或消息结束时渲染
- 工具调用立即显示（不等待完整）
- 摘要消息单独渲染为面板
- 控制spinner的显示和隐藏

### 文件修改清单

1. **修改文件**：`src/application/services/agent/deep/streaming/conversation.py`
2. **修改文件**：`src/application/services/agent/deep/streaming/event_handler.py`

### 数据结构设计

**ToolCallBuffer**：
```python
tool_call_buffers: Dict[str | int, Dict[str, Any]] = {
    "id": str | None,
    "name": str | None,
    "args": str | dict,  # JSON字符串或已解析的dict
    "args_parts": List[str],  # JSON字符串片段
}
```

### 注意事项

1. **兼容性**：确保与单模式流式处理兼容（如果有降级需求）
2. **性能**：文本缓冲不要累积过大，及时刷新
3. **错误处理**：JSON解析失败时要适当处理，不要阻塞显示
4. **状态同步**：确保 `displayed_tool_ids` 和 `tool_call_buffers` 的状态正确管理
5. **测试覆盖**：充分测试各种content_blocks组合场景

