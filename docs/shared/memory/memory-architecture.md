## 记忆模块总体设计

- **核心组件**
  - `SessionStorage`：落盘 JSON，维护 `sessions_index.json`，负责读写「会话 = 消息串」。
  - `GlobalMemoryManager`：面向上层提供统一接口，内存缓存 + 长期存储（依赖 `SessionStorage`），只保存 `HumanMessage`/`AIMessage`。
  - `SessionManager`：CLI 启动时创建/切换/恢复会话，更新 `ctx.session_id`。
  - `UnifiedCheckpointer`：LangGraph 标准接口，读取/写入全局记忆。读取时把历史包装成 `Checkpoint`；写入时过滤 ToolMessage。
  - **会话上下文层（新增）**
    - `SessionContext`：把 `session_id + agent_type + provider + function_type` 标准化，生成 LangGraph 所需的 `thread_id` 与 `checkpoint_ns`。
    - `MemorySyncAdapter`：在运行开始和结束时，同步 MemorySaver（运行时）与 UnifiedCheckpointer（持久化），兼容 fallback。

- **初始化入口**
  - CLI `main._initialize_memory()` 会依次创建 `GlobalMemoryManager`、`SessionManager`、`MemorySyncAdapter`，并放到 `ctx`。
  - 此后 LLM 引擎、basic agent、deep agent 都通过同一个 `ctx` 访问会话和记忆。


---

## LLM 引擎（纯大模型模式）

- **代码路径**
  - 构建时，将 `GlobalMemoryManager` 注入到 LLM 服务（具体适配器内处理）。
  - 每次调用结束后，调用 `GlobalMemoryManager.add_llm_conversation(session_id, user_input, model_output)` 将本轮问答写入。
  - `SessionStorage.save_session()` 负责落盘（JSON 格式）。

- **过程链路**
  1. CLI 初始化 → `ctx.session_id` + `ctx.global_memory` 就绪。
  2. 执行 LLM 请求 → 适配器内调用 `add_llm_conversation`。
  3. `GlobalMemoryManager` 过滤掉系统命令、错误回复等无效信息 → `SessionStorage` 写入文件。
  4. 下次同会话再次调用 → `GlobalChatMessageHistory` 在构造时从磁盘加载历史 → 通过 `RunnableWithMessageHistory` 注入到 Prompt `chat_history` 占位符。

- **特点**
  - 实现简单：只依赖 `GlobalMemoryManager`。
  - 记忆以“问答对”形式保留，不包含工具细节。


---

## Agent 引擎：Basic 模式（`ainvoke` 驱动）

```src/components/shared/memory/global_memory.py```  
```src/components/shared/memory/unified_checkpointer.py```

- **初始化**
  - 基于配置，如果开启记忆，适配器会创建 `UnifiedCheckpointer(storage_dir="data/sessions")`。
  - 创建 Agent Graph 时，直接把该 `checkpointer` 注入 `create_agent()`。

- **执行链路**
  1. 调用 `agent.ainvoke(query, session_id)`：
     - `_build_graph_input()` 生成 `{"messages": [HumanMessage(query)]}`。
     - `_build_graph_config()` 注入 `{"configurable": {"thread_id": session_id}}`。
  2. LangGraph 运行时：
     - 首次节点执行前，`UnifiedCheckpointer.get_tuple()` 会返回历史 `HumanMessage/AIMessage`，LangGraph 注入到当前 State。
     - 执行结束后，`UnifiedCheckpointer.put()` 把最新 `messages` 写回 `GlobalMemoryManager` → `SessionStorage`。
  3. Basic Agent 内部再调用 `_record_session_history()`（通过 `_record_conversation` 或 `save_session`）确保最后回答被持久化（兼容性逻辑）。

- **特点**
  - 完全依赖 LangGraph Checkpointer 机制，代码里无需手动处理历史注入。
  - `session_id` 直接对应 thread_id，最大程度复用官方路径。


---

## Agent 引擎：Deep 模式（流式 `astream` + HITL）

```src/components/shared/memory/session_context.py```  
```src/components/shared/memory/memory_sync.py```  
```src/application/services/agent/deep/streaming/conversation.py```  
```src/agents/deepagents/instances/base_deep_agent.py```

- **双重 Checkpointer 架构**
  - `MemorySaver`（Runtime Checkpointer）：LangGraph 内置内存实现，用于 HITL/中断恢复；每个 deep agent 实例创建 `self.runtime_checkpointer = MemorySaver()`。
  - `UnifiedCheckpointer`（Storage Checkpointer）：仍存储在 `data/sessions/`，通过 `MemorySyncAdapter` 同步。

- **执行链路**
  1. **SessionContext 构造**  
     - `handle_deep_agent_query()` 根据 `session_id + agent_type="deep" + provider + function_type` 创建 `SessionContext`。
     - `session_ctx.build_runtime_config()` 输出 `thread_id` + `checkpoint_ns`，确保不同 provider/功能互不干扰。
  2. **内存预加载**
     - `ctx.memory_sync.load_into_runtime(session_ctx, runtime_checkpointer, runtime_config)`：
       - 调用 `UnifiedCheckpointer.get_tuple()` 取历史；
       - 通过 `MemorySaver.put()` 塞入 runtime；
       - 设置最新 `checkpoint_id` 方便后续增量。
  3. **流式执行**
     - `agent.runtime.astream(...)`，`durability="exit"` 确保完成时写出终态 checkpoint。
     - 如果过程被 HITL 中断，`runtime_checkpointer` 在下一次恢复时可回到中断点（MemorySaver 的职责）。
  4. **结果同步**
     - `memory_sync.persist_from_runtime()`：
       - 优先从 `runtime_checkpointer.get_tuple()` 取最新 checkpoint，过滤 `ToolMessage`，写回 `UnifiedCheckpointer.put()`。
       - 如果 runtime checkpoint 不可用，退化为读取 `event_handler.last_agent_state["messages"]`。
     - 更新 `SessionContext.checkpoint_id`，保证下次加载能拿到最新版本。
  5. **GlobalMemoryManager 同步**
     - `agent.prepare_stream_result()` 内部调用 `_record_conversation()` → `GlobalMemoryManager.add_conversation()` → `SessionStorage.save_session()`，用于“问答摘要”持久化（与 Basic 模式对齐）。

- **特点**
  - 通过 `MemorySyncAdapter` 把 runtime（瞬时状态）与存储（长期记忆）隔离但保持一致。
  - `SessionContext` 对命名空间进行归一化处理（如 `deep::zhipu::research`），避免交叉污染。
  - 流式模式仍能完整复用 basic/LLM 的历史，实现 Agent 引擎的一致体验。


---

## 总体链路对比

|               | LLM 引擎 | Agent Basic | Agent Deep |
|---------------|----------|-------------|------------|
| 引擎入口      | 直接调用模型 | LangGraph `ainvoke` | LangGraph `astream`（含 HITL） |
| 历史载入      | `GlobalMemoryManager.get_session_history()` → `RunnableWithMessageHistory` | LangGraph 自动通过 `UnifiedCheckpointer.get_tuple()` 注入 | `MemorySyncAdapter.load_into_runtime()` 把 `UnifiedCheckpointer` 历史写入 `MemorySaver` |
| 执行中状态    | 无工具状态 | 由 LangGraph 维护 | MemorySaver 维护（HITL/中断） |
| 历史写入      | `add_llm_conversation()` → `SessionStorage` | LangGraph `put()` + Agent 兼容逻辑 | MemorySaver → `MemorySyncAdapter.persist_from_runtime()` → `UnifiedCheckpointer`；同时 `_record_conversation()` 记问答摘要 |
| 命名空间管理  | session_id 直接使用 | session_id 直接使用 | SessionContext 生成 `thread_id` & `checkpoint_ns` |
| ToolMessage 处理 | 无 | 过滤后写入 | 过滤后写入 |
| 长期记忆存储 | `data/sessions/*.json` | 同上 | 同上（与 basic/LLM 共享） |

这样，三种模式共用一套存储与会话体系：`GlobalMemoryManager` 负责落盘，`UnifiedCheckpointer` 在 LangGraph 侧对接，`MemorySyncAdapter` 则弥补 deep 模式原先的缺口，最终实现“LLM ↔ basic agent ↔ deep agent”跨模式共享会话历史。