# IRIS Deep 模式架构优化参考：对照 DeerFlow 的四项建议

本文档整理自对 IRIS（Muti-AI-Agent）与 DeerFlow 架构的对照讨论，供后续重构与文档化使用。文中涉及路径均以仓库根目录 `Muti-AI-Agent/` 为基准。

---

## 文档目的与阅读对象

- **目的**：在不大规模推翻现有实现的前提下，明确「middleware、记忆、提示词、sandbox」四块的可演进方向，并与 DeerFlow 中较清晰的分层做对照。
- **对象**：维护 Deep 模式（`src/components/deepagents`、`src/agents/deepagents`）的开发者。

---

## 一、重新思考 middleware 层的必要性与组织方式

### 1.1 现状简述

`create_deep_agent_runtime`（`src/components/deepagents/runtime.py`）将多类组件统一放入 `middleware` 列表，例如：

- 虚拟文件系统：`VirtualFilesystemMiddleware`
- Shell：`ShellToolMiddleware`（由工厂注入）
- 子代理：`SubAgentMiddleware`
- 横切能力：`SummarizationMiddleware`、`PatchToolCallsMiddleware`、`JsonArgsParserMiddleware`、`ExecutionTimeoutMiddleware`、`HumanInTheLoopMiddleware` 等

该做法与 LangChain / DeepAgents 通过 `create_agent(..., middleware=...)` 扩展行为的方式一致，**技术上合理**。容易混淆的是：**目录名 `runtime_middlewares` 与「一切业务都像 middleware」的心智模型**，使模块分工显得不清。

### 1.2 与 DeerFlow 的对照

DeerFlow 中大致分工为：

- **线程数据与路径**：`ThreadDataMiddleware`、配置类 `Paths`、状态中的 `thread_data`
- **真实执行与隔离**：`Sandbox` 抽象、`SandboxProvider`、工具层对虚拟路径的解析与校验
- **Middleware**：更多承担**横切关注点**（摘要、标题、记忆队列、澄清、循环检测等），以及沙箱生命周期的**薄封装**（如 `SandboxMiddleware`）

IRIS 将「带状态 schema + 注册工具」的能力（虚拟盘、Shell、子代理）放在 middleware 中，在 LangChain 模型下**不可避免**；差异主要在于**包结构与命名是否体现「能力模块」而非「一律叫 middleware」**。

### 1.3 优化建议

| 建议 | 说明 |
|------|------|
| 按职责分包 | 例如 `capabilities/shell/`（内含 `ShellTool`、`PersistentShellSession`、`ShellToolMiddleware` 薄封装）、`capabilities/virtual_filesystem/`、`capabilities/subagents/`。`runtime_middlewares` 可逐步收敛为「仅横切」或改名为 `agent_extensions` 等更贴切的名称（需兼顾 import 迁移成本）。 |
| 区分两类中间件 | **能力类**：扩展 state、注册工具（VFS、Shell、SubAgent）。**横切类**：不定义新业务域，只处理摘要、补丁 tool 消息、超时、HITL 等。在 `runtime.py` 中用两个列表分别构建再合并，并附注释说明顺序依据（类似 DeerFlow `lead_agent/agent.py` 中对 middleware 顺序的注释）。 |
| 接受「部分 middleware 即能力插件」 | 不必为追求「纯净」而拆除 `SubAgentMiddleware`；重点是文档与目录让人知道「改 Shell 去哪、改子代理去哪」。 |

### 1.4 落地切入点（低成本）

在 `runtime.py` 中拆出两个函数（名称可自定）：

- `build_capability_middlewares(...)`：VFS、Shell、SubAgent 等
- `build_cross_cutting_middlewares(...)`：Summarization、PatchToolCalls、JsonArgsParser、Timeout、HITL 等

先改结构与日后再做物理目录迁移，可减小一次性改动风险。

### 1.5 相关代码索引

- `src/components/deepagents/runtime.py`
- `src/components/deepagents/runtime_middlewares/` 各子包
- 对照参考：`deer-flow/backend/packages/harness/deerflow/agents/lead_agent/agent.py`（middleware 链与注释）

---

## 二、记忆系统优化（runtime 与 checkpointer，暂不引入长期记忆）

### 2.1 现状简述

IRIS 已形成**双层**协作（见 `src/application/services/agent/deep/streaming/conversation.py` 与 `src/components/shared/memory/deep_agent_checkpointer.py`）：

1. **运行时**：`SafeMemorySaver` / LangGraph runtime checkpointer，保存当前进程内 thread 的完整图状态（含工具调用、子图等）。
2. **会话持久化**：`DeepAgentCheckpointer` 配合 `SessionStorage`，从 runtime 读取 checkpoint 中的消息，经过滤、去重、裁剪后写入磁盘；若 runtime 中尚无 checkpoint，则通过 `enhance_runtime_input` 从存储加载近期多轮对话再拼接本轮用户消息。

该设计在「无独立长期记忆文件」阶段是务实且可用的。

### 2.2 建议优化方向（不涉及长期记忆 JSON 等）

**术语与文档统一**

在架构说明中固定区分：

- **运行时状态（runtime checkpoint）**：当前执行实例内的 LangGraph 状态。
- **会话持久化（session storage）**：跨重启、按 `session_id` 恢复对话消息子集。
- **长期记忆（未来）**：跨会话的用户画像、事实库等（本文档范围外）。

避免口头「memory」混指 messages、checkpointer 或业务记忆。

**恢复策略可文档化、可测试**

当前逻辑要点：若 runtime 已存在 checkpoint，则不再从 storage 注入历史（由 MemorySaver 延续）。建议在文档或注释中明确：

- 何种场景下「只信任 runtime」
- 进程重启、更换 checkpointer 实现时是否必须走 `enhance_runtime_input`

减少后续排查成本。

**主代理与子代理的持久化边界**

`SubAgentMiddleware` 通过复制 state、排除 `messages` 等与子图交互。需明确：

- 子代理产出哪些通过 `Command` / ToolMessage 写回主图
- 持久化层是否应包含完整 tool 链、如何避免与主会话重复或断裂

与现有 `PatchToolCallsMiddleware`（修补悬空 tool call）形成配套说明。

**可选演进：单一持久化 checkpointer**

若未来希望与 LangGraph 官方示例一致（例如 SQLite / Postgres 单一 saver），可评估用**一个持久化 checkpointer**替代「内存 + 手动 persist」；属架构级变更。在「暂不实现长期记忆」阶段，**优先把现有双层语义写清**投入产出比更高。

### 2.3 相关代码索引

- `src/application/services/agent/deep/streaming/conversation.py`
- `src/components/shared/memory/deep_agent_checkpointer.py`
- `src/components/shared/memory/message_sequence_utils.py`（若涉及裁剪策略）

---

## 三、system prompt 与 XML 标签风格

### 3.1 现状简述

主提示词如 `src/components/deepagents/prompts/main_agent.md` 以 Markdown 标题组织（如「Mission」「Operating Principles」），未采用 `<role>` 等成对标签。对模型而言**并非错误**，可读性也好。

### 3.2 何时引入类 XML 结构

当存在以下需求时，建议对**动态注入块**使用成对标签（标签名团队内统一即可）：

- 多块内容按需开关（子代理列表、工具策略、用户上下文）
- 多块内容由不同模块拼接，需要稳定边界以防串段
- 与 Claude / DeerFlow 系提示习惯对齐，降低模型混淆相邻语义的概率

不必全文改为 XML；可保留外层 Markdown 说明，仅对「注入段」使用标签。

### 3.3 实践建议示例（非强制命名）

- `<subagents>...</subagents>`：可用子代理与委托说明
- `<tools_policy>...</tools_policy>`：工具选用偏好
- `<user_context>...</user_context>`：会话级用户上下文

在 `prompts/registry.py` 或独立「提示词规范」文档中列出**允许使用的标签清单**，避免每人自定义一套。

### 3.4 相关代码索引

- `src/components/deepagents/prompts/main_agent.md`
- `src/components/deepagents/prompts/registry.py`
- 对照参考：`deer-flow/backend/packages/harness/deerflow/agents/lead_agent/prompt.py`

---

## 四、Sandbox 与工作区设计

### 4.1 现状简述

IRIS 当前可理解为「两半」：

1. **虚拟文件系统**：`VirtualFilesystemMiddleware` 提供内存中的路径与工具，与宿主机隔离，适合大块中间结果与子代理间传递。
2. **真实环境**：`real_filesystem` 与 `ShellToolMiddleware`，访问真实磁盘与持久 Shell，配合 `STRICT_POLICY`（`runtime_middlewares/shell/security/policy.py`）及 HITL 审批降低风险。

与 DeerFlow「虚拟路径映射到宿主机目录 + 可选 Docker 容器」属于同一问题域下的不同切分：IRIS 用**内存盘与真机盘分离**，并用审批补强真机操作。

### 4.2 建议借鉴 DeerFlow 的点（不强制上 Docker）

**会话级统一根目录**

DeerFlow 将单会话数据放在 `base_dir/threads/{thread_id}/user-data/` 下，workspace、uploads、outputs 同源。

IRIS 可在配置与实现上收口为**单一的「会话工作区」抽象**（名称可为 `ThreadWorkspace` 或对齐 DeerFlow 的 `Paths` 思想），使：

- Shell 的 `workspace_root`
- 真实文件系统 middleware 的 `project_root` / `resolved_project_root`
- 未来上传与产物目录

默认落在同一会话根下，减少 `conversation.py` 中多处从 `metadata` 解析路径的分散逻辑。

**展示层虚拟路径（可选）**

若希望模型在自然语言与命令中**始终**只看到逻辑路径（如 `/workspace/...`），而避免暴露 `D:\...` 等宿主机路径，可在工具返回与 Shell 输出上做**路径脱敏 / 映射**（思路同 DeerFlow `mask_local_paths_in_output`）。与是否使用 Docker **无关**。

**命名与概念**

- 将「真实命令与磁盘」边界称为 **Sandbox（执行环境）** 或 **HostWorkspace**，与「内存虚拟盘」在文档中区分开。
- 内存盘可称为 **Scratch（草稿区）** 或 **EphemeralStore**，避免多处都叫 filesystem 造成误解。

**审批与隔离的关系**

- **路径白名单 / 会话根**：减少误操作面（DeerFlow 风格）。
- **HITL**：对策略外或高风险操作兜底（IRIS 已有实践）。

二者可并存，而非二选一。

### 4.3 相关代码索引

- `src/components/deepagents/runtime_middlewares/virtual_filesystem/`
- `src/components/deepagents/runtime_middlewares/shell/`
- `src/components/deepagents/runtime_middlewares/real_filesystem/`
- `src/application/services/agent/deep/streaming/conversation.py`（metadata 中的 shell / filesystem 解析）
- 对照参考：`deer-flow/backend/packages/harness/deerflow/config/paths.py`、`sandbox/tools.py`、`sandbox/middleware.py`

---

## 五、小结

| 主题 | 核心结论 |
|------|----------|
| Middleware | 保留 middleware 挂载方式；通过分包、横切与能力分离、组装函数与注释，接近 DeerFlow 的清晰度。 |
| 记忆 | 双层（runtime + 会话存储）合理；优先统一术语、文档化恢复策略与子代理边界，长期记忆后续单独立项。 |
| 提示词 | Markdown 可保留；对动态注入块按需引入成对标签并固定词表。 |
| Sandbox | 统一会话根、可选展示层虚拟路径、命名区分内存盘与真机执行区；审批与白名单互补。 |

---

## 六、修订记录

| 日期 | 说明 |
|------|------|
| 2026-03-23 | 初稿：基于 IRIS 与 DeerFlow 对照讨论整理四项建议 |
