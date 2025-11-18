# Deep 模式记忆系统问题分析与解决方案

## 问题背景

在实现跨模式（Basic/Deep/LLM）的统一会话记忆系统时，遇到了 LangGraph checkpoint 机制的兼容性问题。本文档记录了问题的根本原因、尝试的解决方案以及最终的重构方案。

## 核心问题

### 1. channel_versions 类型不兼容

**问题表现：**
```
TypeError: '>' not supported between instances of 'str' and 'int'
```

**根本原因：**
- **LangGraph runtime（Deep 模式）** 使用 MemorySaver，其内部生成的 `channel_versions` 格式为字符串，如：
  ```python
  "00000000000000000000000000000003.0.6383896473525281"
  ```

- **UnifiedCheckpointer（统一存储）** 最初使用整数格式：
  ```python
  {"messages": len(messages)}  # int
  ```

- 当两种格式的 checkpoint 混合在同一个 MemorySaver 中时，LangGraph 执行以下操作会失败：
  - `max(checkpoint["channel_versions"].values())` - 比较所有 version 找最大值
  - `if v > previous_versions.get(k, null_version)` - 比较新旧 version

**错误发生位置：**
1. `langgraph/pregel/_algo.py:261` - `apply_writes` 函数中的 `max()` 调用
2. `langgraph/pregel/_utils.py:28` - `get_new_channel_versions` 函数中的比较操作

### 2. get_next_version 不支持字符串

**问题表现：**
```
NotImplementedError in get_next_version
```

**根本原因：**
- LangGraph 的 `BaseCheckpointSaver.get_next_version()` 实现如下：
  ```python
  def get_next_version(self, current: V | None, channel: None) -> V:
      if isinstance(current, str):
          raise NotImplementedError  # 直接抛出异常
      elif current is None:
          return 1
      else:
          return current + 1
  ```

- 当 Basic 模式尝试读取包含字符串 version 的 checkpoint 时，无法生成下一个 version

### 3. 架构设计冲突

**核心矛盾：**
- **统一存储需求**：希望 Basic、Deep、LLM 三种模式共享同一个会话历史
- **checkpoint 机制差异**：
  - Basic/LLM 模式使用简单的 MemorySaver（整数 version）
  - Deep 模式使用带状态恢复的 MemorySaver（字符串 version）
  - 两者的 checkpoint 结构和 version 管理机制不兼容

## 尝试的解决方案

### 方案 1：统一使用字符串 channel_versions

**实施：**
- 修改 UnifiedCheckpointer 和 memory_sync，使用字符串格式的 channel_versions
- 格式：`f"{len(messages):032d}.0.0"`

**结果：**
- 解决了 `'>' not supported` 错误（同类型可比较）
- 引入新问题：Basic 模式读取 Deep 模式创建的 checkpoint 时触发 `NotImplementedError`
- 原因：Basic 模式的 MemorySaver 无法为字符串 version 生成下一个 version

**结论：失败**

### 方案 2：存储使用整数，runtime 使用字符串

**实施：**
- UnifiedCheckpointer 恢复使用整数 channel_versions
- 在 `persist_from_runtime` 时，将 runtime 的字符串 version 规范化为整数
- 在 `load_into_runtime` 时，将整数 version 转换为字符串（理论上）

**遇到的问题：**
- Deep 模式的 runtime 会自己生成新的 checkpoint（字符串 version）
- 从 storage 加载的 checkpoint（整数 version）和 runtime 生成的 checkpoint（字符串 version）混合在同一个 MemorySaver 中
- 再次触发 `'>' not supported` 错误

**结论：失败**

### 方案 3：禁用 Deep 模式的 load_into_runtime

**实施：**
- 注释掉 Deep 模式 streaming conversation 中的 `load_into_runtime` 调用
- 依赖 `enhance_runtime_input` 将历史消息注入到输入中
- Deep 模式的 runtime checkpointer 独立运行（不从 storage 加载）

**遇到的问题：**
- 仍然失败，因为 `load_into_runtime` 在其他地方（如 `BaseDeepAgent.invoke`）仍然被调用
- 没有完全阻止 storage checkpoint 和 runtime checkpoint 的混合

**结论：失败**

## 根本原因分析

经过多次尝试，我们认识到问题的本质：

1. **LangGraph 的 checkpoint 机制是紧耦合的**
   - channel_versions 的类型和格式由 checkpointer 实现决定
   - 不同类型的 version 无法在同一个 checkpointer 实例中混合使用

2. **Deep 模式有特殊的状态管理需求**
   - HITL（Human-in-the-Loop）需要保存完整的执行状态
   - 需要保存 ToolMessage 和 __interrupt__ 等中间状态
   - 这些状态与 Basic/LLM 模式的简单消息历史有本质区别

3. **强行统一会导致系统脆弱**
   - 需要在多个位置进行类型转换和格式规范化
   - 容易在不同的执行路径中遗漏处理
   - 维护成本高，容易引入新的 bug

## 重构方案

### 核心思路：会话隔离

**原则：**
不再强求所有模式共享同一个底层 checkpoint 系统，而是按照模式特性分离存储。

### 目录结构

```
data/
├── basicagent_llm/
│   └── sessions/           # Basic 和 LLM 模式共享
│       ├── session_xxx/
│       │   └── messages.json
│       └── ...
└── deepagent/
    └── sessions/           # Deep 模式独立
        ├── session_xxx/
        │   ├── checkpoints/    # 包含完整 checkpoint 数据
        │   └── messages.json   # 仅用于跨模式查询
        └── ...
```

### 设计要点

1. **Basic 和 LLM 模式**
   - 共享 `basicagent_llm/sessions` 目录
   - 使用简单的消息列表存储
   - channel_versions 使用整数格式
   - 轻量级，快速读写

2. **Deep 模式**
   - 独立使用 `deepagent/sessions` 目录
   - 保存完整的 LangGraph checkpoint（包括字符串 version）
   - 支持 HITL 状态恢复
   - 可选：额外保存一份 messages.json 用于跨模式历史查询

3. **跨模式切换**
   - Basic/LLM ↔ Deep：不再共享同一个 checkpoint
   - 如需查看历史，可从各自的 messages.json 中读取
   - 接受模式切换时历史不完全同步的限制（合理的设计取舍）

### 实施步骤

1. 修改 GlobalMemoryManager，支持按模式分离存储路径
2. 为 Deep 模式创建独立的 checkpointer（直接使用 LangGraph 的 MemorySaver 或 SQLite）
3. 移除 load_into_runtime 中的类型转换逻辑
4. 更新 session_context 的 thread_id 生成逻辑，包含模式标识
5. 测试各模式的独立工作和历史管理

### 优势

1. **架构清晰**：每个模式使用最适合自己的存储方式
2. **类型安全**：不再需要在运行时进行类型转换
3. **易于维护**：减少了跨模式的耦合和兼容性处理
4. **扩展性好**：未来增加新模式时不会影响现有模式

### 限制与取舍

1. **历史不完全共享**：模式切换后不能继续前一个模式的对话上下文
2. **存储空间增加**：Deep 模式需要保存更多的 checkpoint 数据
3. **实现复杂度**：需要维护两套存储路径和管理逻辑

## 总结

经过深入的问题排查和多次尝试，我们发现 LangGraph 的 checkpoint 机制在类型和格式上的严格要求，使得统一管理不同模式的会话历史变得不切实际。

重构方案通过会话隔离的方式，接受了模式间历史不完全共享的限制，换取了更清晰的架构、更好的类型安全和更低的维护成本。这是一个合理的工程权衡。
