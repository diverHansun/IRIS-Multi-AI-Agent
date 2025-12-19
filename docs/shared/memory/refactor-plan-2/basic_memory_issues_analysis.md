# Basic Agent 内存问题深度分析与重构建议

## 问题复现

### 问题1：`/restore` 后切换 engine 失效

**操作序列：**
```
1. agent:BASIC[S] > /sessions              # 查看会话列表
2. agent:BASIC[S] > /restore user_20251119_174058_fa26ae22  # 切换到某个会话
   -> Switched to session: user_20251119_174058_fa26ae22
3. agent:BASIC[S] > /switch llm             # 切换引擎
   -> LLM engine initialized. session_id = user_20251211_214856_b6a6f5ea (最近的会话)
```

**预期行为**：切换引擎后仍然保持 `user_20251119_174058_fa26ae22` 会话
**实际行为**：切换引擎后自动加载了最近的会话

### 问题2：历史消息被清空

**操作序列：**
```
1. agent:BASIC[S] > /restore user_20251119_174058_fa26ae22
   -> Session has 6 messages
2. agent:BASIC[S] > 我们之前聊了什么？  # 发送一条新消息
   -> AI Response: "我无法记住之前的对话..."
3. Check file: data/llm_basicagent/sessions/user_20251119_174058_fa26ae22.json
   -> Only 2 messages remain! (原来的 6条消息全部丢失)
```

**预期行为**：新消息追加到历史之后，文件应该有 8 条消息
**实际行为**：原有的 6 条历史消息被覆盖，只剩下刚才的 2 条消息

---

## 根本原因分析

### 问题1根因：强制加载最近会话

**代码位置**：`src/application/commands/engine_commands.py:53-80`

```python
if current_mode == "deep" or current_mode != new_mode:
    # Create new memory manager for llm/basic mode
    ctx.global_memory = GlobalMemoryManager(agent_mode=new_mode, max_messages=50)
    ctx.session_manager = SessionManager(ctx.global_memory, mode=new_mode)
    ctx.memory_sync = MemorySyncAdapter(ctx.global_memory, agent_mode=new_mode)

    # Reload session from correct storage
    if hasattr(ctx, "session_manager") and ctx.session_manager:
        recent_session = ctx.session_manager.get_most_recent_session()  # 问题所在
        if recent_session:
            ctx.session_id = recent_session["session_id"]  # 覆盖了用户通过 /restore 设置的值
```

**问题链条**：
1. 用户通过 `/restore` 设置 `ctx.session_id = "user_20251119_174058_fa26ae22"`
2. 用户执行 `/switch llm`，触发引擎切换
3. 系统创建新的 `GlobalMemoryManager` 实例（这是合理的，因为 basic 和 llm 模式可能使用不同的存储）
4. 但是，系统随后强制调用 `get_most_recent_session()` 并覆盖 `ctx.session_id`
5. 用户之前通过 `/restore` 设置的会话ID丢失

### 问题2根因：内存分离导致的覆盖式保存

#### 架构回顾：Basic Agent 的双层内存

Basic Agent 使用了**双层内存架构**：

```
┌─────────────────────────────────────┐
│  BasicAgent (running)               │
│  ┌───────────────────────────────┐  │
│  │  MemorySaver (checkpointer)   │  │ <-- 运行时层（内存）
│  │  - storage: defaultdict       │  │     LangGraph 状态管理
│  │  - thread_id -> checkpoint    │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
              │ (agent state)
              ↓ persist_from_runtime()
┌─────────────────────────────────────┐
│  GlobalMemoryManager                │
│  ┌───────────────────────────────┐  │
│  │  SessionStorage               │  │ <-- 持久化层（磁盘）
│  │  - data/llm_basicagent/       │  │     JSON 文件
│  │  - session_id.json            │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**问题链条**：

1. **初始状态**：
   - 文件 `user_20251119_174058_fa26ae22.json` 中有 6 条历史消息
   - MemorySaver (checkpointer) 中没有该 session 的状态（因为刚切换引擎/刚恢复会话）

2. **用户发送消息**：
   - BasicAgent.invoke() 调用 `graph.ainvoke({"messages": [HumanMessage("我们之前聊了什么？")]}, config={"configurable": {"thread_id": "user_20251119_174058_fa26ae22"}})`
   - LangGraph 在 MemorySaver 中第一次为这个 thread_id 运行
   - MemorySaver 中没有历史状态，所以 agent 只看到当前这一条消息
   - Agent 回复："我无法记住之前的对话..."
   - LangGraph 自动调用 `MemorySaver.put()` 保存这一轮的状态（只有 2 条消息）

3. **持久化同步**（`src/application/services/agent/basic/conversation.py:43-48`）：
   ```python
   ctx.memory_sync.persist_from_runtime(
       session_ctx,
       agent.checkpointer,  # MemorySaver
       None,
       result,  # agent 返回的结果，包含 messages
   )
   ```

4. **persist_from_runtime 逻辑**（`src/components/shared/memory/memory_sync.py:111-199`）：
   ```python
   # 从 agent_state 或 checkpointer 中提取 messages
   messages_to_persist = agent_state.get("messages", [])  # 只有 2 条消息

   # 过滤、去重
   filtered = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]
   deduplicated = self._deduplicate_messages(filtered)

   # 覆盖式保存！
   self.storage.save_session(session_ctx.session_id, deduplicated)  # 只保存 2 条消息
   ```

5. **结果**：
   - 文件中原有的 6 条消息被完全覆盖
   - 只剩下刚才的 2 条消息

#### 为什么 MemorySaver 中没有历史？

**关键点**：MemorySaver 是进程内存中的 checkpointer，当发生以下情况时会丢失状态：

1. **进程重启** - CLI 重启后内存清空
2. **引擎切换** - 切换引擎时创建新的 `GlobalMemoryManager`，但 BasicAgent 的 `checkpointer` 是在 agent 创建时初始化的
3. **会话切换（/restore）** - 切换到另一个 session_id 时，如果该 session_id 在当前 checkpointer 中没有历史，就是空的

**验证**：查看 BasicAgent 初始化代码

`src/agents/basicagents/adapters/base_adapter.py` 中：
```python
checkpointer = MemorySaver() if enable_memory else None
```

这个 MemorySaver 实例是在 agent 创建时生成的，不会从 SessionStorage 加载历史！

#### LangGraph MemorySaver API 分析

从源码 `.venv/Lib/site-packages/langgraph/checkpoint/memory/__init__.py:132-213` 可以看到：

```python
class InMemorySaver(BaseCheckpointSaver):
    """An in-memory checkpoint saver."""

    def __init__(self):
        self.storage = defaultdict(lambda: defaultdict(dict))  # thread_id -> checkpoint_ns -> checkpoint_id -> checkpoint
        self.writes = defaultdict(dict)
        self.blobs = defaultdict()

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        if checkpoints := self.storage[thread_id][checkpoint_ns]:
            # 返回最新的 checkpoint
            checkpoint_id = max(checkpoints.keys())
            return checkpoints[checkpoint_id]
        return None  # 如果没有，返回 None

    def put(self, config, checkpoint, metadata, new_versions):
        """保存 checkpoint 到内存"""
        thread_id = config["configurable"]["thread_id"]
        self.storage[thread_id][...] = checkpoint
```

**关键发现**：
- MemorySaver 没有 `load_from_file` 或类似的方法来加载外部历史
- 它只管理内存中的 checkpoint
- 如果某个 thread_id 在 MemorySaver 中不存在，`get_tuple` 返回 `None`，LangGraph 就认为这是一个全新的对话

---

## 设计原则回顾

从 `docs/langchain-architecture/architecture.md` 中提取的设计原则：

### SOLID 原则

1. **单一职责原则 (SRP)**：每个模块只负责一件事
2. **开闭原则 (OCP)**：对扩展开放，对修改封闭
3. **里氏替换原则 (LSP)**：子类可以替换父类
4. **接口隔离原则 (ISP)**：不应该强迫客户依赖它们不使用的接口
5. **依赖倒置原则 (DIP)**：依赖抽象，不依赖具体实现

### 已有的设计模式应用

- **工厂模式**：AgentFactory, LLMManager
- **适配器模式**：LLMAdapter, ToolAdapter
- **单例模式**：GlobalMemoryManager (带线程安全)
- **策略模式**：ToolProvider
- **模板方法模式**：BaseAgent (计划中)
- **观察者模式**：配置热重载 (计划中)

### 架构分层

```
Application Layer (CLI, GUI, FastAPI)
      ↓
Engine Layer (LLM, Agent Basic, Agent Deep)
      ↓
Component Layer (Memory, Tools, LLM)
      ↓
Infrastructure Layer (Config, Storage, Logging)
```

---

## 现有的内存架构回顾

从 `docs/shared/memory/old-arch/memory-architecture.md` 和 `docs/shared/memory/refactor-plan/deep_memory_problems_analysis.md`：

### 当前架构

```
┌──────────────────────────────────────────────────────────┐
│                  Shared Storage Layer                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │  SessionStorage (JSON files)                       │  │
│  │  - data/llm_basicagent/sessions/*.json             │  │
│  │  - data/deepagent/sessions/*.json                  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
                          ↑
                          │ (read/write)
        ┌─────────────────┴─────────────────┐
        │                                   │
┌───────┴────────┐                 ┌────────┴─────────┐
│  LLM Mode      │                 │  Agent Basic     │
│  - direct      │                 │  - MemorySaver   │
│    GlobalMem   │                 │  - persist_from_ │
│    add_llm_    │                 │    runtime()     │
│    conver...   │                 └──────────────────┘
└────────────────┘
                                   ┌────────────────────┐
                                   │  Agent Deep        │
                                   │  - MemorySaver     │
                                   │  - MemorySyncA...  │
                                   │  - isolated        │
                                   └────────────────────┘
```

### 问题总结

1. **LLM Mode** - 正常工作
   - 直接使用 `GlobalMemoryManager.add_llm_conversation()`
   - 没有双层内存问题

2. **Agent Basic Mode** - 存在问题
   - 使用 MemorySaver (运行时) + SessionStorage (持久化)
   - 两层内存不同步，导致覆盖式保存

3. **Agent Deep Mode** - 设计合理（隔离式）
   - 独立的存储路径
   - 完整的 checkpoint 保存（支持 HITL）
   - 不与 Basic/LLM 模式共享底层 checkpoint

---

## 解决方案设计

### 方案对比

| 方案 | 描述 | 优点 | 缺点 | 实施难度 | 推荐度 |
|------|------|------|------|---------|-------|
| **A. 同步加载** | 在 agent 运行前，从 SessionStorage 加载历史到 MemorySaver | - 最小改动<br>- 保留现有架构 | - MemorySaver API 不支持外部加载<br>- 需要手动构造 checkpoint | 高 | 不推荐 |
| **B. 合并式保存** | persist_from_runtime 时，先读取现有历史，再合并新消息 | - 不丢失历史<br>- 逻辑简单 | - 每次保存都要读文件（性能）<br>- 可能有并发问题 | 低 | 临时方案 |
| **C. 移除 MemorySaver** | Basic Agent 直接使用 GlobalMemoryManager，放弃 LangGraph checkpoint | - 彻底解决双层内存问题<br>- 与 LLM 模式对齐 | - 需要重构 BasicAgent<br>- 失去 LangGraph checkpoint 的优势 | 很高 | 需要评估 |
| **D. 自定义 Checkpointer** | 实现 SessionStorageCheckpointer，直接读写 JSON 文件 | - 统一内存架构<br>- 符合 LangGraph 设计 | - 实现复杂<br>- 需要理解 LangGraph checkpoint 协议 | 中高 | 推荐（长期） |

### 推荐方案：D. 自定义 Checkpointer + B. 临时修复

#### 短期修复（方案B）：合并式保存

**实施步骤**：

1. 修改 `MemorySyncAdapter.persist_from_runtime()` (`src/components/shared/memory/memory_sync.py:111-199`)

```python
def persist_from_runtime(
    self,
    session_ctx: SessionContext,
    runtime_checkpointer: Any,
    runtime_config: Optional[Dict[str, Any]] = None,
    agent_state: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Persist runtime state to storage with merge strategy.

    CRITICAL: This method preserves all historical messages by merging
    with existing storage instead of replacing.
    """
    config = session_ctx.build_runtime_config(runtime_config)

    # Extract messages from agent_state or runtime checkpoint
    messages_to_persist: List[Any] = []
    if isinstance(agent_state, dict):
        state_messages = agent_state.get("messages") or []
        if isinstance(state_messages, list):
            messages_to_persist = state_messages

    if not messages_to_persist and runtime_checkpointer is not None:
        # Fallback: try runtime checkpoint
        try:
            checkpoint_tuple = runtime_checkpointer.get_tuple(config)
            if checkpoint_tuple:
                checkpoint_copy = checkpoint_tuple.checkpoint.copy()
                channel_values = dict(checkpoint_copy.get("channel_values", {}))
                messages_to_persist = channel_values.get("messages", [])
        except Exception as exc:
            logger.warning(f"Failed to read runtime checkpoint: {exc}")

    # Flatten and filter messages
    flattened = self._flatten_messages(messages_to_persist)
    filtered = [
        m for m in flattened
        if isinstance(m, (HumanMessage, AIMessage))
    ]

    if not filtered:
        logger.warning(f"No messages to persist for session {session_ctx.session_id}")
        return

    # NEW: Load existing messages from storage
    existing_messages = self.storage.load_session(session_ctx.session_id) or []
    logger.debug(f"Loaded {len(existing_messages)} existing messages from storage")

    # NEW: Merge existing + new messages
    all_messages = existing_messages + filtered

    # ENHANCED: Deduplicate across all messages
    deduplicated = self._deduplicate_messages(all_messages)

    if len(deduplicated) < len(all_messages):
        logger.info(
            f"Removed {len(all_messages) - len(deduplicated)} duplicate messages "
            f"(existing: {len(existing_messages)}, new: {len(filtered)})"
        )

    try:
        # Save merged messages
        self.storage.save_session(session_ctx.session_id, deduplicated)
        logger.debug(
            f"Persisted {len(deduplicated)} messages for session {session_ctx.session_id} "
            f"(merged from {len(existing_messages)} existing + {len(filtered)} new)"
        )
    except Exception as exc:
        logger.error(f"Failed to persist messages to storage: {exc}")
```

**优点**：
- 快速修复问题2（历史消息被清空）
- 代码改动最小
- 向后兼容

**缺点**：
- 每次保存都要读取文件（性能开销）
- 没有解决根本的架构问题（双层内存不同步）

2. 修改 `/switch` 命令，保留用户选择的 session_id (`src/application/commands/engine_commands.py:69-80`)

```python
# Reload session from correct storage
if hasattr(ctx, "session_manager") and ctx.session_manager:
    # NEW: Preserve user-selected session_id from /restore
    if ctx.session_id and ctx.session_manager.memory_manager.session_exists(ctx.session_id):
        # User has explicitly selected a session via /restore, keep it
        logger.info(f"Preserving user-selected session: {ctx.session_id}")
        ctx.console.print(f"[dim]Kept current session: {ctx.session_id}[/]")
    else:
        # No valid session, load the most recent one
        recent_session = ctx.session_manager.get_most_recent_session()
        if recent_session:
            ctx.session_id = recent_session["session_id"]
            logger.info(f"Loaded recent {new_mode} session: {ctx.session_id}")
            ctx.console.print(f"[dim]Loaded recent {new_mode} session: {ctx.session_id}[/]")
        else:
            # No existing session, create new one
            ctx.session_id = ctx.session_manager.create_new_session()
            logger.info(f"Created new {new_mode} session: {ctx.session_id}")
            ctx.console.print(f"[dim]Created new {new_mode} session: {ctx.session_id}[/]")
```

**优点**：
- 完全解决问题1（/restore 后切换 engine 失效）
- 符合用户预期

#### 长期重构（方案D）：自定义 SessionStorageCheckpointer

**设计目标**：
- 统一 Basic Agent 的双层内存为单层
- 直接使用 SessionStorage 作为 LangGraph checkpointer
- 保持与 LangGraph 的兼容性

**实现方案**：

1. 创建 `SessionStorageCheckpointer` 继承 `BaseCheckpointSaver`

```python
# src/components/shared/memory/session_storage_checkpointer.py

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple, Checkpoint
from typing import Optional, Dict, Any
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .session_storage import SessionStorage

class SessionStorageCheckpointer(BaseCheckpointSaver):
    """
    LangGraph checkpointer backed by SessionStorage (JSON files).

    This checkpointer directly reads/writes to SessionStorage, eliminating
    the dual-memory problem in Basic Agent mode.

    Design principles:
    - SRP: Only responsible for checkpoint persistence, not in-memory caching
    - LSP: Fully compatible with LangGraph's BaseCheckpointSaver interface
    - OCP: Extensible through SessionStorage configuration
    """

    def __init__(self, storage_dir: str = "data/llm_basicagent/sessions"):
        super().__init__()
        self.storage = SessionStorage(storage_dir)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """
        Load checkpoint from SessionStorage.

        LangGraph will call this before graph execution to restore state.
        """
        thread_id = config["configurable"]["thread_id"]  # = session_id

        # Load messages from JSON file
        messages = self.storage.load_session(thread_id)
        if not messages:
            return None

        # Convert to LangGraph checkpoint format
        checkpoint = self._messages_to_checkpoint(messages)

        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata={"session_id": thread_id},
            pending_writes=[],
            parent_config=None,
        )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: Dict[str, Any],
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        """
        Save checkpoint to SessionStorage.

        LangGraph will call this after graph execution to persist state.
        """
        thread_id = config["configurable"]["thread_id"]

        # Extract messages from checkpoint
        messages = self._checkpoint_to_messages(checkpoint)

        # Filter: only keep HumanMessage and AIMessage
        filtered = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]

        # Save to JSON file
        self.storage.save_session(thread_id, filtered, metadata=metadata)

        return config

    def _messages_to_checkpoint(self, messages: List[BaseMessage]) -> Checkpoint:
        """Convert messages list to LangGraph checkpoint format."""
        return {
            "id": f"checkpoint_{len(messages)}",
            "channel_values": {
                "messages": messages,
            },
            "channel_versions": {
                "messages": len(messages),  # Use int version (compatible with Basic mode)
            },
            "versions_seen": {},
        }

    def _checkpoint_to_messages(self, checkpoint: Checkpoint) -> List[BaseMessage]:
        """Extract messages from LangGraph checkpoint."""
        channel_values = checkpoint.get("channel_values", {})
        return channel_values.get("messages", [])

    def get_next_version(self, current: Optional[int], channel: None) -> int:
        """Get next version number (integer-based, compatible with Basic mode)."""
        if current is None:
            return 1
        return current + 1
```

2. 修改 BasicAgent 适配器使用新的 checkpointer

```python
# src/agents/basicagents/adapters/base_adapter.py

from src.components.shared.memory import SessionStorageCheckpointer

async def create_agent(
    self,
    provider: str,
    model: str,
    tools: List[BaseTool],
    config: BasicAgentConfig,
) -> BaseBasicAgent:
    """Create agent instance with SessionStorageCheckpointer."""

    # Create checkpointer backed by SessionStorage
    if config.agent_params["memory_enabled"]:
        # NEW: Use SessionStorageCheckpointer instead of MemorySaver
        checkpointer = SessionStorageCheckpointer(
            storage_dir=config.agent_params.get("storage_dir", "data/llm_basicagent/sessions")
        )
    else:
        checkpointer = None

    # ... rest of agent creation
```

3. 移除 `persist_from_runtime` 调用（不再需要）

```python
# src/application/services/agent/basic/conversation.py

async def handle_agent_query(ctx, query: str) -> str:
    """Handle agent query without manual persistence."""
    config = _get_agent_config(ctx)
    agent = config.get("agent_instance")

    with ctx.console.status("[dim]Agent reasoning...[/]"):
        result = await agent.ainvoke(query, session_id=ctx.session_id)

    # REMOVED: persist_from_runtime call
    # LangGraph will automatically call SessionStorageCheckpointer.put()

    if result.get("success"):
        answer = result.get("output", "")
        ctx.console.print(f"[bold blue]BasicAgent >[/] {answer}")
        return answer

    # ... error handling
```

**优点**：
- 彻底解决双层内存问题
- 统一内存架构，单一数据源
- 符合 SRP 原则（SessionStorageCheckpointer 只负责持久化）
- 自动同步，无需手动调用 persist
- 性能优化：LangGraph 只在需要时调用 get/put

**实施路径**：

```
Phase 1: 实现 SessionStorageCheckpointer (1-2 天)
  ├─ 创建 SessionStorageCheckpointer 类
  ├─ 实现 get_tuple / put / get_next_version
  └─ 单元测试

Phase 2: 重构 BasicAgent 适配器 (1 天)
  ├─ 修改 create_agent 使用新 checkpointer
  ├─ 移除 persist_from_runtime 调用
  └─ 集成测试

Phase 3: 清理冗余代码 (1 天)
  ├─ 移除 MemorySyncAdapter 中 Basic 模式相关代码
  ├─ 更新文档
  └─ 回归测试
```

---

## 总结与建议

### 问题本质

这两个问题揭示了 Basic Agent 模式中**内存架构不一致**的根本缺陷：

1. **双层内存不同步**：MemorySaver (运行时) 和 SessionStorage (持久化) 各自为政
2. **生命周期管理缺失**：引擎切换时没有正确处理 session 状态迁移
3. **覆盖式保存的危险**：persist_from_runtime 没有考虑已有历史

### 建议实施策略

**立即行动**（本周内）：
1. 实施**方案B**（合并式保存）+ 修复 /switch 命令
   - 快速止损，防止用户数据丢失
   - 影响范围小，风险可控

**中期重构**（2-3周内）：
2. 实施**方案D**（SessionStorageCheckpointer）
   - 彻底解决架构问题
   - 为 LangGraph 1.0 迁移做准备
   - 统一 Basic/LLM 模式的内存管理

**长期优化**（1-2个月）：
3. 考虑模板方法模式统一 Agent 基类
   - 参考 architecture.md 中的设计模式建议
   - 减少 BasicAgent / DeepAgent 的代码重复
   - 统一初始化流程和内存管理

### 架构改进方向

```
现在 (有问题):
  BasicAgent → MemorySaver (内存) → persist_from_runtime() → SessionStorage (磁盘)
                    ↑ 不同步 ↑

改进后:
  BasicAgent → SessionStorageCheckpointer → SessionStorage (磁盘)
                    ↑ 单一数据源 ↑
```

### 与 Deep Agent 的对比

| 维度 | Basic Agent (现状) | Basic Agent (改进后) | Deep Agent (现状) |
|------|-------------------|---------------------|------------------|
| Checkpointer | MemorySaver | SessionStorageCheckpointer | MemorySaver |
| 存储位置 | data/llm_basicagent/ | data/llm_basicagent/ | data/deepagent/ |
| 内存层数 | 2层（运行时+持久化）| 1层（统一持久化）| 2层（运行时+持久化）|
| 同步机制 | persist_from_runtime | LangGraph 自动 | MemorySyncAdapter |
| HITL 支持 | 不支持 | 不支持 | 支持 |
| 状态恢复 | 不支持 | 不支持 | 支持 |

**设计理念**：
- **Basic Agent**：轻量级，快速响应，简单记忆
- **Deep Agent**：完整状态管理，支持复杂工作流和人机协作

---

## 参考文档

- [LangGraph Checkpoint Documentation](https://langchain-ai.github.io/langgraph/reference/checkpoints/)
- [SOLID Principles in Python](https://realpython.com/solid-principles-python/)
- [Architecture Design (v3.0.0)](../../../docs/langchain-architecture/architecture.md)
- [Memory System Architecture](../old-arch/memory-architecture.md)
- [Deep Memory Problems Analysis](./deep_memory_problems_analysis.md)
- [Memory System Refactoring Plan](./memory_system_refactoring_plan1.md)
