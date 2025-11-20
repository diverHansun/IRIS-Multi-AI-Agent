# Deep Agent 超时处理机制优化方案

## 一、当前超时问题分析

### 1.1 两层超时机制

Deep Agent 运行时存在两种超时限制：

| 超时类型 | 配置位置 | 作用范围 | 默认值 | 异常类型 |
|---------|---------|---------|--------|---------|
| `step_timeout` | `runtime_config` | 单个 LangGraph 节点执行 | 300s | `TimeoutError` |
| `max_execution_time` | `safety_config` | 整个 Agent 生命周期 | 600s | 无异常（优雅跳转） |

### 1.2 `step_timeout` 问题与解决

#### 问题表现
- 单步执行超时时抛出 `TimeoutError`
- 用户查询未持久化，会话状态丢失
- Agent 无法感知超时，无法制定重试策略

#### 已实现的解决方案
**位置**: `src/application/services/agent/deep/streaming/conversation.py:187-262`

**处理流程**:
1. 捕获 `TimeoutError` 异常
2. 持久化已完成的工作到 JSON（包括用户查询）
3. 通过 `aupdate_state` 向 Agent 发送系统通知（方括号 `HumanMessage`）
4. `MessageFilter` 自动过滤系统通知，不污染持久化历史
5. 用户可继续对话

**核心代码**:
```python
except TimeoutError as exc:
    # 1. 持久化状态
    checkpoint_tuple = runtime_checkpointer.get_tuple(runtime_config)
    if checkpoint_tuple:
        complete_state = checkpoint_tuple.checkpoint.get("channel_values")
        agent_memory_sync.persist_from_runtime(session_ctx, runtime_checkpointer, runtime_config, complete_state)
    else:
        # 早期超时：手动保存用户查询
        storage.save_session(session_ctx.session_id, existing_messages + [HumanMessage(content=query)])
    
    # 2. 通知 Agent（SystemMessage会被自动过滤，不会持久化）
    await agent.runtime.aupdate_state(
        runtime_config,
        values={"messages": [SystemMessage(content="SYSTEM NOTIFICATION: The previous operation timed out...")]}
    )
```

**设计原则应用**:
- **SOLID-SRP**: 持久化、通知、过滤各司其职
- **DRY**: `MessageFilter` 统一处理所有系统通知过滤
- **KISS**: 使用SystemMessage类型而非方括号标记，更简洁可靠

### 1.3 `max_execution_time` 问题

#### 问题表现
- `ExecutionTimeoutMiddleware` 通过 `jump_to: "end"` 优雅终止
- 添加 `AIMessage` 说明超时原因
- 用户体验问题：
  - 超时消息伪装成正常 AI 回复，不醒目
  - `AIMessage` 被持久化到 JSON，污染对话历史
  - 用户说"继续"时，Agent 看到超时消息可能困惑

#### 当前实现机制
**位置**: `src/components/deepagents/runtime_middlewares/timeout.py:115-151`

```python
@hook_config(can_jump_to=["end"])
def before_model(self, state, runtime):
    elapsed = time.time() - start_time
    if elapsed >= self.max_execution_time:
        return {
            "jump_to": "end",
            "messages": [AIMessage("Agent execution timed out after {elapsed:.2f} seconds...")]
        }
```

**问题根源**:
- Middleware 跳转不触发异常，只是正常的状态更新
- 无法从事件流中区分"正常结束"和"超时结束"
- 超时 `AIMessage` 已进入 Runtime State，难以移除

## 二、优化方案设计

### 2.1 方案目标

1. 恢复会话历史：确保对话记忆不中断
2. 持久化存储：超时后自动保存已完成的工作
3. 用户体验一致：与 `step_timeout` 保持相同的处理流程
4. 对话历史干净：过滤超时系统消息

### 2.2 检测方案

#### 方案 A：Middleware 状态标记（推荐）

**实现**: 在 `ExecutionTimeoutMiddleware` 添加标记字段

```python
# timeout.py
class ExecutionTimeoutState(AgentState):
    execution_start_time: NotRequired[Annotated[float, UntrackedValue, PrivateStateAttr]]
    _max_execution_timeout: NotRequired[Annotated[float, UntrackedValue]]  # 新增

def before_model(self, state, runtime):
    if elapsed >= self.max_execution_time:
        return {
            "jump_to": "end",
            "messages": [AIMessage(timeout_message)],
            "_max_execution_timeout": elapsed,  # 标记超时
        }
```

**检测逻辑**:
```python
# conversation.py
checkpoint = runtime_checkpointer.get_tuple(runtime_config)
state = checkpoint.checkpoint.get("channel_values", {})
timeout_elapsed = state.get("_max_execution_timeout")

if timeout_elapsed is not None:
    _handle_max_execution_timeout(...)
```

**优点**:
- 可靠：不依赖字符串匹配
- 明确：语义清晰的状态标记
- 最小侵入：只在 Middleware 添加一个字段

**SOLID 原则**:
- **OCP**: 扩展 Middleware 功能，不修改核心逻辑
- **SRP**: 超时检测与处理分离

#### 方案 B：时间判断 + 消息内容（备选）

```python
# conversation.py
elapsed = time.perf_counter() - start_time
if deadline and elapsed >= max_execution_time * 0.95:
    last_msg = messages[-1] if messages else None
    if isinstance(last_msg, AIMessage) and "timed out" in last_msg.content.lower():
        _handle_max_execution_timeout(...)
```

**优点**: 不需修改 Middleware

**缺点**: 依赖字符串匹配，脆弱

### 2.3 处理流程

#### 统一处理函数设计

```python
async def _handle_max_execution_timeout(
    ctx,
    session_ctx,
    runtime_checkpointer,
    runtime_config,
    agent_memory_sync,
    agent,
    original_query: str,
    elapsed_time: float,
    max_time: float,
) -> None:
    """
    处理 max_execution_time 超时，确保会话记忆不中断。
    
    职责：
    1. 用户通知：显示醒目警告
    2. 状态清理：移除超时 AIMessage
    3. 持久化：保存干净的对话历史
    4. Agent 通知：发送系统通知（方括号）
    """
    logger.warning(f"Max execution time exceeded: {elapsed:.1f}s / {max_time}s")
    
    # 1. 用户通知
    ctx.console.print("[bold red]MAXIMUM EXECUTION TIME EXCEEDED[/]")
    ctx.console.print(f"[yellow]Agent ran for {elapsed:.1f}s (limit: {max_time}s)[/]")
    ctx.console.print("[dim]Saving conversation state...[/]")
    
    # 2. 获取并清理状态
    checkpoint_tuple = runtime_checkpointer.get_tuple(runtime_config)
    if not checkpoint_tuple:
        logger.error("No checkpoint after timeout")
        return
    
    complete_state = checkpoint_tuple.checkpoint.get("channel_values", {})
    messages = list(complete_state.get("messages", []))
    
    # 移除超时 AIMessage（最后一条）
    if messages and isinstance(messages[-1], AIMessage):
        if "Agent execution timed out" in messages[-1].content:
            messages = messages[:-1]
            logger.debug(f"Removed timeout AIMessage")
    
    # 3. 持久化干净的历史
    if agent_memory_sync:
        try:
            # 先更新 Runtime State（移除超时消息）
            await agent.runtime.aupdate_state(
                runtime_config,
                values={"messages": messages}
            )
            
            # 再持久化到 JSON
            agent_memory_sync.persist_from_runtime(
                session_ctx,
                runtime_checkpointer,
                runtime_config,
                {**complete_state, "messages": messages},
            )
            
            human_ai_count = len([m for m in messages if isinstance(m, (HumanMessage, AIMessage))])
            ctx.console.print(f"[dim]Conversation saved ({human_ai_count} messages).[/]")
            logger.info("Conversation persisted after max_execution_time timeout")
        except Exception as exc:
            logger.error(f"Failed to persist: {exc}", exc_info=True)
            ctx.console.print("[yellow]Warning: Could not save conversation[/]")
    
    # 4. 通知 Agent（SystemMessage会被 MessageFilter 自动过滤）
    ctx.console.print("[dim]Notifying agent about timeout...[/]")
    try:
        from langchain_core.messages import SystemMessage
        await agent.runtime.aupdate_state(
            runtime_config,
            values={
                "messages": [
                    SystemMessage(
                        content=f"SYSTEM NOTIFICATION: Maximum execution time ({max_time}s) exceeded after {elapsed:.1f}s. "
                        f"The conversation state has been saved and you can continue working."
                    )
                ]
            },
        )
        ctx.console.print("[dim]Agent notified. You can continue the conversation.[/]")
        logger.info("Agent notified about timeout")
    except Exception as update_exc:
        logger.error(f"Failed to notify agent: {update_exc}")
        ctx.console.print("[yellow]Warning: Could not notify agent[/]")
```

#### 调用位置

```python
# conversation.py
async def handle_deep_agent_query(ctx, query: str) -> str:
    # ... (流式执行)
    
    # 流式结束后检测
    checkpoint = runtime_checkpointer.get_tuple(runtime_config)
    state = checkpoint.checkpoint.get("channel_values", {})
    timeout_elapsed = state.get("_max_execution_timeout")
    
    if timeout_elapsed is not None:
        # 处理 max_execution_time 超时
        await _handle_max_execution_timeout(
            ctx, session_ctx, runtime_checkpointer, runtime_config,
            agent_memory_sync, agent, query, timeout_elapsed, max_execution_time
        )
        return "[Timeout occurred - please retry or rephrase your request]"
    
    # 正常持久化流程
    if agent_memory_sync:
        agent_memory_sync.persist_from_runtime(...)
    
    return answer
```

### 2.4 设计原则总结

| 原则 | 应用体现 |
|-----|---------|
| **KISS** | 使用方括号标记系统消息，简单直观 |
| **YAGNI** | 只实现必要功能，不添加配置开关 |
| **SOLID-SRP** | `_handle_max_execution_timeout` 单一职责：超时恢复 |
| **SOLID-OCP** | 扩展 Middleware 状态，不修改核心逻辑 |
| **DRY** | 复用 `MessageFilter` 的系统通知过滤机制 |

## 三、实施计划

### 3.1 文件修改清单

1. **`src/components/deepagents/runtime_middlewares/timeout.py`**
   - 扩展 `ExecutionTimeoutState` 添加 `_max_execution_timeout` 字段
   - 在 `before_model` 返回值中添加超时标记

2. **`src/application/services/agent/deep/streaming/conversation.py`**
   - 添加 `_handle_max_execution_timeout` 函数
   - 在流式结束后检测 `_max_execution_timeout` 并处理

3. **测试验证**
   - 创建 `tests/unit/timeout/test_max_execution_time.py`
   - 验证超时检测、状态清理、持久化、Agent 通知

### 3.2 测试场景

| 场景 | 预期结果 |
|-----|---------|
| Agent 在 600s 内完成 | 正常结束，无超时处理 |
| Agent 运行超过 600s | 触发超时处理，显示红色警告 |
| 超时后查看 JSON 历史 | 不包含超时 `AIMessage` |
| 超时后用户说"继续" | Agent 能看到完整对话历史 + 系统通知（Runtime） |
| 超时后重启程序 | 加载干净的历史，无超时消息 |

### 3.3 风险评估

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| Middleware 修改影响其他模块 | 低 | 只添加可选字段，向后兼容 |
| `aupdate_state` 失败 | 中 | 异常捕获，降级处理 |
| 消息移除逻辑错误 | 中 | 字符串匹配 + 位置检查双重验证 |

## 四、与 `step_timeout` 的一致性

### 4.1 行为对齐

| 维度 | `step_timeout` | `max_execution_time` |
|-----|---------------|---------------------|
| 用户警告 | `[yellow]TIMEOUT[/]` | `[bold red]MAXIMUM EXECUTION TIME EXCEEDED[/]` |
| 持久化 | 保存已完成工作 | 保存已完成工作（移除超时消息） |
| Agent 通知 | 方括号 `HumanMessage` | 方括号 `HumanMessage` |
| 历史过滤 | `MessageFilter` 自动过滤 | `MessageFilter` 自动过滤 |
| 用户继续 | 支持 | 支持 |

### 4.2 差异化处理

- `step_timeout`: 黄色警告（单步问题，可重试）
- `max_execution_time`: 红色警告（总时间耗尽，更严重）

## 五、后续优化方向

### 5.1 自动重试机制

当 `step_timeout` 发生时，可考虑自动重试：

```python
retry_count = 0
max_retries = 2

while retry_count < max_retries:
    try:
        # 执行 Agent
        break
    except TimeoutError:
        retry_count += 1
        if retry_count < max_retries:
            ctx.console.print(f"[yellow]Retrying ({retry_count}/{max_retries})...[/]")
        else:
            # 最终失败处理
```

### 5.2 动态超时调整

根据任务复杂度动态调整超时时间：

```python
# 检测到多步工具链时延长超时
if tool_calls > 5:
    adjusted_timeout = step_timeout * 1.5
```

### 5.3 超时预警

在接近超时前提示用户：

```python
if elapsed > max_execution_time * 0.8:
    ctx.console.print("[yellow]Note: Approaching time limit (80% used)[/]")
```

## 六、总结

本方案通过在 `ExecutionTimeoutMiddleware` 添加状态标记，实现了 `max_execution_time` 超时的可靠检测与恢复。核心改进包括：

1. **记忆不中断**: 超时后完整保存已完成的对话
2. **历史干净**: 过滤超时系统消息，不污染持久化存储
3. **体验一致**: 与 `step_timeout` 保持相同的用户交互流程
4. **Agent 感知**: 通过系统通知让 Agent 了解超时情况

设计严格遵循 SOLID 原则，确保代码简洁、可维护、可扩展。

---

## 七、实施进展 (Implementation Progress)

### Phase 1: 消息机制完善 (已完成 ✓)

**时间**: 2025-11-20

**目标**: 将系统通知从方括号标记的 `HumanMessage` 迁移到 `SystemMessage`，实现更可靠的类型过滤。

**修改文件**:
1. `src/components/shared/storage/message_filter.py`
   - 从内容匹配改为类型检测: `isinstance(message, (SystemMessage, ToolMessage))`
   - KISS 原则：类型检查比正则匹配更简洁可靠

2. `src/components/shared/storage/session_storage.py`
   - 处理 SystemMessage 反序列化（向后兼容）
   - 对持久化数据中出现的 SystemMessage 发出警告

3. `src/components/shared/memory/memory_sync.py`
   - 统一过滤逻辑：只保留 `HumanMessage` 和 `AIMessage`
   - 自动排除 `SystemMessage`、`ToolMessage` 及其他类型

4. `src/application/services/agent/deep/streaming/conversation.py`
   - 所有超时通知改用 `SystemMessage`
   - 更新 `step_timeout` 异常处理

**测试验证**:
- `test_message_filtering.py`: 6/6 测试通过
  - SystemMessage 识别 ✓
  - ToolMessage 识别 ✓
  - 消息过滤正确性 ✓

**结论**: 类型过滤机制完成，为 Phase 2 铺平道路。

---

### Phase 2: 统一持久化与超时异常处理 (已完成 ✓)

**时间**: 2025-11-20

**目标**: 采用"方案B"（异常抛出）替代 `jump_to="end"`，实现干净的 checkpoint 和统一的异常处理流程。

#### 2.1 durability="exit" 行为研究

**测试文件**: `test_durability_exit.py`

**关键发现**:
1. `durability="exit"` 仅在**正常完成**时保存 checkpoint
2. 异常（TimeoutError、ExecutionTimeoutError 等）**不会**触发 checkpoint 保存
3. **必须**在每个异常处理块中显式调用 `persist_from_runtime`
4. `jump_to="end"` 会将超时 `AIMessage` 添加到 checkpoint，污染历史
5. 抛出异常可保持 checkpoint 干净

**测试结果**: 5/5 测试通过

#### 2.2 核心实现

##### 2.2.1 统一持久化 Helper (DRY 原则)

**文件**: `src/application/services/agent/deep/streaming/conversation.py`

**新增函数**: `_persist_conversation_state()`

```python
async def _persist_conversation_state(
    ctx,
    session_ctx: SessionContext,
    runtime_checkpointer,
    runtime_config: Dict[str, Any],
    agent_memory_sync: Optional[MemorySyncAdapter],
    reason: str = "normal"
) -> bool:
    """
    统一持久化 helper，从 runtime checkpoint 提取状态并持久化。
    自动过滤 SystemMessage/ToolMessage。

    参数:
        reason: 持久化原因 ("normal", "step_timeout", "max_execution_time", 等)

    返回:
        bool: 是否成功持久化
    """
```

**调用场景**:
- 正常完成
- `step_timeout` (TimeoutError)
- `max_execution_time` (ExecutionTimeoutError)
- 未来: KeyboardInterrupt、其他异常

##### 2.2.2 ExecutionTimeoutMiddleware 改为异常抛出

**文件**: `src/components/deepagents/runtime_middlewares/timeout.py`

**关键变更**:

**之前** (方案A - jump_to):
```python
@hook_config(can_jump_to=["end"])
def before_model(self, state, runtime):
    if elapsed >= self.max_execution_time:
        return {
            "jump_to": "end",
            "messages": [AIMessage("Agent execution timed out...")]  # 污染 checkpoint!
        }
```

**现在** (方案B - 异常):
```python
def before_model(self, state, runtime):
    if elapsed >= self.max_execution_time:
        raise ExecutionTimeoutError(elapsed, self.max_execution_time)  # 干净的 checkpoint!
```

**新增异常类**:
```python
class ExecutionTimeoutError(Exception):
    """Agent 执行总时长超时异常"""

    def __init__(self, elapsed_time: float, max_execution_time: float) -> None:
        self.elapsed_time = elapsed_time
        self.max_execution_time = max_execution_time
        super().__init__(
            f"Execution time limit exceeded: {elapsed_time:.2f}s / {max_execution_time:.2f}s"
        )
```

**优势**:
- ✓ 保持 checkpoint 干净（无超时 AIMessage）
- ✓ 与 `step_timeout` 处理逻辑统一
- ✓ 便于日志记录和监控
- ✓ 符合 Python 异常处理惯例

##### 2.2.3 统一异常处理流程

**文件**: `src/application/services/agent/deep/streaming/conversation.py`

**新增异常处理块**:
```python
except ExecutionTimeoutError as exc:
    # Max execution time exceeded (方案B: middleware raises exception)
    logger.warning(f"Max execution time exceeded: {exc}")

    # 1. 持久化干净的 checkpoint (无超时 AIMessage)
    await _persist_conversation_state(
        ctx, session_ctx, runtime_checkpointer,
        runtime_config, agent_memory_sync,
        reason="max_execution_time"
    )

    # 2. 通知 Agent (SystemMessage 会被自动过滤，不会持久化)
    await agent.runtime.aupdate_state(
        runtime_config,
        values={
            "messages": [
                SystemMessage(
                    content=f"SYSTEM NOTIFICATION: Maximum execution time ({exc.max_execution_time:.0f}s) "
                    f"exceeded after {exc.elapsed_time:.1f}s. The conversation has been saved."
                )
            ]
        },
    )

    # 3. 通知用户
    ctx.console.print(f"[bold red]MAX EXECUTION TIME EXCEEDED[/]: {exc.elapsed_time:.1f}s")
```

**重构后的 `step_timeout` 处理**:
```python
except TimeoutError as exc:
    logger.warning(f"Step timeout: {exc}")

    # 使用统一 helper
    await _persist_conversation_state(
        ctx, session_ctx, runtime_checkpointer,
        runtime_config, agent_memory_sync,
        reason="step_timeout"
    )

    # 通知 Agent
    await agent.runtime.aupdate_state(...)
```

#### 2.3 测试验证

**测试文件**: `test_phase2_timeout_handling.py`

**测试覆盖**:
1. `ExecutionTimeoutError` 异常类正确定义 ✓
2. Middleware 抛出异常（方案B）而非 jump_to ✓
3. `SystemMessage`/`ToolMessage` 过滤正确 ✓
4. `_persist_conversation_state` helper 签名正确 ✓

**测试结果**: 4/4 测试通过

#### 2.4 设计原则应用

| 原则 | 应用体现 |
|------|---------|
| **SOLID-SRP** | `_persist_conversation_state` 单一职责：持久化状态 |
| **DRY** | 统一 helper 消除重复的持久化逻辑 |
| **KISS** | 类型检测代替字符串匹配 |
| **YAGNI** | 只实现必要功能，不添加配置开关 |

#### 2.5 方案对比总结

| 维度 | 方案A (jump_to) | 方案B (异常) ✓ |
|------|----------------|---------------|
| Checkpoint 污染 | ✗ 有超时 AIMessage | ✓ 干净 |
| 异常处理统一 | ✗ 需特殊检测逻辑 | ✓ 与 step_timeout 一致 |
| 用户体验 | ✗ 超时消息伪装成 AI 回复 | ✓ SystemMessage 醒目 |
| 代码复杂度 | 中（需清理消息） | ✓ 低（无需清理） |
| 日志追踪 | 中（需状态标记） | ✓ 易（异常栈） |

**最终选择**: **方案B（异常抛出）** ✓

---

### Phase 3: SubAgent 超时处理 (已完成 ✓)

**时间**: 2025-11-20

**目标**: 扩展超时处理到 SubAgent,确保 SubAgent 超时时 MainAgent 状态能正确持久化。

#### 3.1 架构设计

**核心挑战**:
- SubAgent 无 checkpointer (设计为无状态)
- SubAgent 超时不应中断 MainAgent
- SubAgent 的 `task` 工具无法直接访问 MainAgent 的持久化上下文

**解决方案**:
1. **共享持久化 helper**: 提取到 `src/components/shared/persistence/helpers.py`
2. **上下文注入**: conversation.py 将持久化上下文注入到 `runtime_input`
3. **上下文排除**: SubAgent 不接收持久化上下文 (通过 `_EXCLUDED_STATE_KEYS`)
4. **异常捕获**: SubAgent task 工具捕获超时,持久化 MainAgent,返回错误消息

#### 3.2 核心实现

##### 3.2.1 共享持久化 Helper (DRY 原则)

**新文件**: `src/components/shared/persistence/helpers.py`

**目的**: 消除 MainAgent 和 SubAgent 之间的代码重复

```python
async def persist_conversation_state(
    session_ctx: "SessionContext",
    runtime_checkpointer,
    runtime_config: Dict[str, Any],
    agent_memory_sync: Optional["MemorySyncAdapter"],
    reason: str = "normal",
    ctx=None
) -> bool:
    """
    Unified persistence helper for MainAgent and SubAgent handlers.

    - Extracts state from runtime checkpointer
    - Automatically filters SystemMessage/ToolMessage
    - Saves to persistent storage (data/sessions/*.json)
    """
```

**调用者**:
- `conversation.py`: MainAgent 超时处理
- `subagents/middleware.py`: SubAgent 超时处理

##### 3.2.2 上下文注入机制

**文件**: `src/application/services/agent/deep/streaming/conversation.py`

**实现**: 将持久化上下文注入到 `runtime_input`

```python
# Inject persistence context into state for SubAgent access
if isinstance(runtime_input, dict):
    runtime_input["_session_ctx"] = session_ctx
    runtime_input["_memory_sync"] = agent_memory_sync
    runtime_input["_runtime_checkpointer"] = runtime_checkpointer
    runtime_input["_runtime_config"] = runtime_config
```

**设计考虑**:
- 使用 `_` 前缀表明内部使用
- 通过 `runtime.state` 传递,避免修改构造函数
- SubAgent 通过 `_EXCLUDED_STATE_KEYS` 自动过滤

##### 3.2.3 SubAgent 超时处理

**文件**: `src/components/deepagents/runtime_middlewares/subagents/middleware.py`

**关键变更**:

**1. 排除持久化上下文**:
```python
_EXCLUDED_STATE_KEYS = (
    "messages",
    "todos",
    "_session_ctx",           # 不传递给 SubAgent
    "_memory_sync",
    "_runtime_checkpointer",
    "_runtime_config",
)
```

**2. SubAgent 持久化 helper**:
```python
async def _persist_main_agent_if_available(
    runtime: ToolRuntime,
    reason: str
) -> bool:
    """从 runtime.state 提取上下文并调用共享 helper"""
    # 提取上下文
    session_ctx = runtime.state.get("_session_ctx")
    memory_sync = runtime.state.get("_memory_sync")
    runtime_checkpointer = runtime.state.get("_runtime_checkpointer")
    runtime_config = runtime.state.get("_runtime_config")

    if not all([session_ctx, memory_sync, runtime_checkpointer, runtime_config]):
        return False  # 优雅降级

    # 调用共享 helper
    return await persist_conversation_state(...)
```

**3. 异常处理更新**:
```python
# task 工具内部
except TimeoutError as exc:
    # step_timeout: 持久化 + 返回错误消息
    await _persist_main_agent_if_available(
        runtime, reason=f"subagent_{subagent_type}_step_timeout"
    )
    return "[TIMEOUT] SubAgent step execution timed out..."

except ExecutionTimeoutError as exc:
    # max_execution_time: 持久化 + 返回详细错误
    await _persist_main_agent_if_available(
        runtime, reason=f"subagent_{subagent_type}_max_execution_timeout"
    )
    return f"[TIMEOUT] SubAgent max execution time exceeded..."
```

#### 3.3 测试验证

**测试文件**: `test_phase3_subagent_timeout.py`

**测试覆盖**:
1. 共享持久化 helper 签名正确 ✓
2. SubAgent 持久化 helper 存在 ✓
3. 持久化上下文被正确排除 ✓
4. SubAgent 导入 ExecutionTimeoutError ✓
5. conversation.py 使用共享 helper ✓
6. Mock 超时持久化流程 ✓

**测试结果**: 6/6 测试通过

#### 3.4 设计原则应用

| 原则 | 应用体现 |
|------|---------|
| **SOLID-SRP** | 共享 helper 单一职责：持久化状态 |
| **DRY** | MainAgent + SubAgent 共用同一 helper |
| **KISS** | 通过 runtime.state 传递上下文,无需复杂架构 |
| **YAGNI** | 不保存 SubAgent 中间状态 (无 checkpointer) |
| **Fail-safe** | SubAgent 超时不中断 MainAgent,优雅降级 |

#### 3.5 数据流图

```
[MainAgent] conversation.py
    |
    | 1. 注入上下文到 runtime_input
    |    (_session_ctx, _memory_sync, ...)
    |
    v
[MainAgent] runtime.state
    |
    | 2. 调用 SubAgent (task 工具)
    |
    v
[SubAgent] task 函数
    |
    | 3. 提取上下文 (runtime.state.get(...))
    | 4. 执行 SubAgent (可能超时)
    |
    v
[SubAgent] 超时异常
    |
    | 5. _persist_main_agent_if_available()
    |    -> persist_conversation_state()
    |    -> 持久化 MainAgent 状态
    |
    v
[SubAgent] 返回错误消息给 MainAgent
    |
    v
[MainAgent] 接收错误,继续运行或重试
```

#### 3.6 对比总结

| 维度 | Phase 2 (MainAgent) | Phase 3 (SubAgent) ✓ |
|------|--------------------|-----------------------|
| **持久化范围** | MainAgent 状态 | MainAgent 状态 (不保存 SubAgent) |
| **异常传播** | 抛出到 conversation.py | 捕获并返回错误消息 |
| **上下文访问** | 直接访问 | 通过 runtime.state 提取 |
| **用户体验** | 中断,需"继续" | MainAgent 继续运行 |
| **代码复用** | 独立实现 | ✓ 共享 helper |

---

### Phase 4: 后续计划

1. **集成测试**: 端到端测试所有超时场景
   - MainAgent step_timeout
   - MainAgent max_execution_time
   - SubAgent step_timeout
   - SubAgent max_execution_time
2. **性能优化**: 持久化性能监控与优化
3. **文档完善**: 更新用户文档和 API 文档

---

### 实施总结

**完成时间**: 2025-11-20

**修改文件**: 9 个核心文件
**测试文件**: 4 个测试套件（21 个单元测试，全部通过）

**核心成果**:
1. ✓ 消息机制从内容匹配升级到类型过滤 (Phase 1)
2. ✓ 超时处理从 jump_to 迁移到异常抛出 (Phase 2)
3. ✓ 统一持久化逻辑，消除重复代码 (Phase 2)
4. ✓ Checkpoint 保持干净，历史记录可靠 (Phase 2)
5. ✓ SubAgent 超时自动持久化 MainAgent 状态 (Phase 3)
6. ✓ 共享持久化 helper,代码复用 (Phase 3)

**架构改进**:
- 更清晰的职责分离（SRP）
- 更少的代码重复（DRY）
- 更简单的实现（KISS）
- 更统一的异常处理
- 更好的容错能力（Fail-safe）

**下一步**: 集成测试 + 性能优化


