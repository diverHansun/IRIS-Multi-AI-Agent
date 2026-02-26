# ToolMessage 持久化：实施计划

## 阶段划分

基于问题依赖关系，分为 4 个阶段：

```
Phase A: SessionStorage 序列化层 (P1, P2)           ← 基础层，后续所有变更依赖此
Phase B: Checkpointer 过滤/截断/去重 (P1, P4, P5, P6, P10)  ← 核心逻辑层
Phase C: MessageFilter 同步 (P7)                    ← 周边影响
Phase D: Deep 模式 per-step 持久化 (P8, P9)         ← 含 durability 前置变更
```

Phase A → B 有强依赖。Phase C, D 可在 B 完成后并行。

---

## Phase A: SessionStorage 序列化层

### 目标
扩展 `_message_to_dict` 和 `_dict_to_message`，使 SessionStorage 能够正确序列化/反序列化 AIMessage.tool_calls 和 ToolMessage。

### 步骤

A1. 在 `session_storage.py` 顶部增加截断常量：
   - `MAX_TOOL_CONTENT_LENGTH = 500`
   - `TOOL_CONTENT_TRUNCATION_SUFFIX = "\n... [truncated, {original_length} chars total]"`

A2. 扩展 `_message_to_dict`：
   - AIMessage 分支：检查 `tool_calls` 属性，非空时序列化为 `[{name, args, id}]` 列表
   - 新增 ToolMessage 分支：序列化 `content`（截断）、`tool_call_id`、`name`
   - HumanMessage 分支不变

A3. 扩展 `_dict_to_message`：
   - AIMessage 分支：读取 `tool_calls` 字段（默认 `[]`），传入 `AIMessage(content=..., tool_calls=...)`
   - 新增 ToolMessage 分支：构造 `ToolMessage(content=..., tool_call_id=..., name=...)`
   - 移除旧的 ToolMessage 转 HumanMessage 兼容逻辑（用正式反序列化替代）

### 验证清单
- [ ] 旧 session 文件（无 tool_calls）可正常加载
- [ ] AIMessage.tool_calls 序列化后反序列化保持一致
- [ ] ToolMessage 序列化后 content 不超过 MAX_TOOL_CONTENT_LENGTH + suffix
- [ ] ToolMessage 反序列化后 tool_call_id 和 name 保持一致
- [ ] 单元测试覆盖：空 tool_calls、多 tool_calls、超长 content 截断

---

## Phase B: Checkpointer 过滤/截断/去重

### 目标
修改两个 Checkpointer 的消息处理管线，正确处理 ToolMessage。

### 步骤

B1. 两个 checkpointer 的 `_filter_messages` 增加 ToolMessage：
   - 导入 `ToolMessage`
   - isinstance 检查增加 `ToolMessage`

B2. 实现 `_split_into_atomic_groups(messages)` 辅助方法：
   - 扫描消息列表，识别 AIMessage(tool_calls) + 对应 ToolMessage 的原子组
   - 返回 `List[List[BaseMessage]]`
   - 此方法供两个 checkpointer 共用（可提取到公共基类或独立函数）

B3. 改写 `_trim_messages`：
   - 调用 `_split_into_atomic_groups`
   - 从最新组开始向前累加，直到消息总数超过 `max_messages`
   - 返回保留的消息列表

B4. 修正 BasicAgentCheckpointer 的 `_deduplicate_messages`：
   - ToolMessage 使用 `tool_call_id` 作为去重 key

B5. 修正 DeepAgentCheckpointer 的 `_deduplicate_messages`：
   - 连续 ToolMessage 使用 `tool_call_id` 判断重复

B6. 修改 DeepAgentCheckpointer 的 `enhance_runtime_input`：
   - 新增 `_extract_recent_turns(messages, max_turns)` 方法
   - 将 `max_history` 语义从消息数改为 turn 数
   - 默认值保持 10 turn（10 turn × 3-5 msg = 30-50 条消息，在 max_messages=100 范围内）

B7. 移除 DeepAgentCheckpointer 的 `persist_from_runtime` 中无用加载（P10）：
   - 删除 `existing = self.storage.load_session(session_id) or []` 及对应 debug log
   - 当前是 "direct replacement" 策略，existing 从未参与后续逻辑
   - 在 per-step 持久化场景下，每步都做无用磁盘读取属于浪费

### 考虑点：公共逻辑提取

`_split_into_atomic_groups` 和 `_trim_messages` 的逻辑在两个 checkpointer 中完全相同。可选方案：
- 方案 a: 提取到公共模块（例如 `message_utils.py`）作为独立函数
- 方案 b: 在两个 checkpointer 中分别实现（代码重复但解耦）
- 推荐方案 a，因为原子组截断逻辑较复杂且必须保持一致

### 验证清单
- [ ] 包含 ToolMessage 的消息序列可正确 persist 和 reload
- [ ] 截断后的消息序列通过 `_validate_chat_history()` 验证
- [ ] 截断不会将原子组拆散
- [ ] 去重不会删除不同 tool_call_id 的 ToolMessage
- [ ] `enhance_runtime_input` 按 turn 计数，加载正确数量的历史
- [ ] 端到端测试：Deep 模式完整执行 → 退出 → 重新加载 → 继续对话

---

## Phase C: MessageFilter 同步

### 目标
更新 MessageFilter 以正确处理 ToolMessage。

### 步骤

C1. 修改 `is_system_notification`：
   - 移除 ToolMessage 的 isinstance 检查
   - 仅保留 SystemMessage

C2. 修改 `filter_message_history`：
   - ToolMessage 作为普通消息保留
   - 确保不破坏消息序列

C3. 检查 MessageFilter 的所有调用点：
   - 确认修改不会产生意外副作用

### 验证清单
- [ ] `is_system_notification(ToolMessage(...))` 返回 False
- [ ] `filter_message_history` 保留 ToolMessage
- [ ] 所有调用点功能正常

---

## Phase D: Deep 模式 Per-Step 持久化

### 目标
在 streaming loop 中增加中间崩溃保护。

### 步骤

D1. **前置：durability 变更（P9）**
   - 在 `conversation.py` 的 `astream()` 调用中移除 `durability="exit"` 参数
   - LangGraph 将使用默认值 `"async"`
   - 这使 MemorySaver 每步异步更新，`persist_from_runtime()` 可读到最新状态
   - 影响分析：对 HITL 无影响；对性能无影响（MemorySaver 是内存操作）

D2. 扩展 `EventHandlerResult` 数据类：
   - 增加 `step_completed: bool = False` 字段

D3. 在 `event_handler.py` 中检测 tool 执行完成事件：
   - 识别 `updates` 事件中 "tools" node 的输出
   - 设置 `step_completed = True`

D4. 在 `conversation.py` 的 streaming loop 中：
   - 检测 `result.step_completed`
   - 调用 `deep_checkpointer.persist_from_runtime()`
   - 异常处理：persist 失败仅 warning，不影响 agent 执行

### 验证清单
- [ ] durability 变更后 HITL 中断/恢复功能正常
- [ ] durability 变更后 MemorySaver 在 mid-stream 有中间状态
- [ ] tool 执行完成后，session 文件已更新
- [ ] persist 失败不中断 agent 执行
- [ ] 正常完成时的最终 persist 仍然执行（最终一致性）
- [ ] I/O 频率在可接受范围内（< 50ms per persist）

---

## 提交策略

```
Commit 1: Phase A (SessionStorage 序列化扩展)
Commit 2: Phase B (Checkpointer 消息管线修正)
Commit 3: Phase C (MessageFilter 同步)
Commit 4: Phase D (Per-step 持久化)
```

Phase C 较小，可考虑合并到 Commit 2 中。

---

## 风险矩阵

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 原子组截断算法实现错误 | agent reload 时 crash | 充分的单元测试覆盖边界情况 |
| AIMessage.tool_calls 序列化格式不兼容 | 旧 LangChain 版本无法反序列化 | tool_calls 使用简单 dict 格式，不依赖 LangChain 内部类型 |
| durability 变更影响 HITL | HITL 中断/恢复失败 | HITL 依赖 `__interrupt__` 机制，与 durability 无关；但需端到端测试验证 |
| per-step persist I/O 影响性能 | agent 执行变慢 | 异步写入或限制 persist 频率（最多每 N 秒一次） |
| ToolMessage 内容截断丢失关键信息 | LLM 上下文不完整 | 截断阈值硬编码 500 字符，后续按需提升为配置项 |
| MessageFilter 调用点遗漏 | 某些代码路径仍在过滤 ToolMessage | Phase C 中全面排查调用点 |
