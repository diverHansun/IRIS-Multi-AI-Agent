## Deep 模式 HITL 持久化问题

### 现状概述
- Deep 模式当前在运行时直接使用 `UnifiedCheckpointer` 作为 LangGraph 的 checkpointer。
- 该组件为了控制体积，在 `put()` 中只保留 `HumanMessage` 与 `AIMessage`，会过滤掉 `ToolMessage`、`__interrupt__` 等执行态信息。
- HITL 审批后再执行 `Command(resume=...)` 时，LangGraph 无法从 checkpoint 恢复工具上下文，导致第二次 streaming 立即结束，任务中断。

### 优化思路
- 将“运行时状态恢复”和“长期对话持久化”拆开处理：
  1. **运行时**交由 `MemorySaver`（或等价的 in-memory checkpointer）管理，确保 HITL / 工具调用的完整数据可写入、可恢复。
  2. **会话持久化**继续使用 `UnifiedCheckpointer`（或现有 `GlobalMemoryManager` 逻辑），只在 streaming 结束后落盘经筛选的 Human/AI 消息。
- 代码层面可以在 deep agent runtime 初始化时：
  - 若启用 HITL / 工具中断，则默认注入 `MemorySaver`。
  - 仍保留现有持久化逻辑，用于记录最终对话历史。

### Basic 模式是否需要 MemorySaver？
- 目前 Basic 模式未启用 HITL 或多轮工具中断，`UnifiedCheckpointer` 即可满足持久化需求。
- 若未来在 Basic 模式引入类似的暂停/恢复能力，再考虑引入 `MemorySaver` 或其他 runtime checkpointer。

