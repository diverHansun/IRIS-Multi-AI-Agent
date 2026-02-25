# Shell 工作目录问题分析

> **文档定位**: 问题诊断文档，描述根因链路、代码级分析与影响范围。
>
> **关联文档**:
> [design-proposal.md](./design-proposal.md) — 方案设计（配置语义、服务层职责、数据流）
> [implementation-plan.md](./implementation-plan.md) — 实施步骤（修改清单、测试方案、风险评估）

---

## 术语约定

| 术语 | 含义 | 代码对应 |
|------|------|---------|
| **项目目录** | 用户运行 iris 命令时所在的目录 | `ProjectContext.project_path` |
| **进程 CWD** | Python 进程的当前工作目录 | `Path.cwd()` / `os.getcwd()` |
| **应用根目录** | iris 源代码的安装/存放目录 | 如 `D:\Projects\Langchain\Muti-AI-Agent` |
| **workspace_root** | shell 会话的工作目录，由配置决定 | `ShellConfig.workspace_root` |

> **核心区分**: 进程 CWD ≠ 项目目录。当 iris 以可执行文件安装时，
> 进程 CWD 为应用根目录，而用户期望 shell 在自己的项目目录中执行。

---

## 1. 问题现象

当 deep agent 使用 shell 工具执行 bash 命令时，无论 iris 从哪个目录启动，
shell 的工作目录始终为 `D:\Projects\Langchain\Muti-AI-Agent`（应用根目录），
而非用户的项目目录。

**期望行为**: shell 工作目录应为 iris 进程的启动目录（即用户的项目目录）。

**问题本质**: 运行时上下文（`project_context`）与静态配置（`shell.json`）之间的断裂。

---

## 2. 根因链路

### 2.1 端到端调用链（含 project_context 可用性标注）

下图展示了从 iris 启动到 shell 进程创建的完整调用链路。
每个节点用 ✅/❌ 标注 `project_context` 的传递状态，断裂点一目了然。

```
用户启动 iris → ProjectContext.from_cwd() 捕获项目目录
    │
    v
[应用层] create_default_deep_agent(ctx)               // ctx.project_context: ✅ 可用
    │
    v
[应用层] _instantiate_agent(ctx, ...)                  // ctx.project_context: ✅ 可用
    │   构建 DeepAgentCheckpointer(project_context=...)
    │
    v
[管理层] deep_agent_manager.create_deep_agent(...)     // project_context: ✅ via checkpointer
    │   middleware_config 参数未传入 → fallback 到 registry 加载静态配置
    │
    v
[管理层] DeepAgentManager.create_agent(...)            // project_context: ✅ via checkpointer
    │   middleware_cfg = middleware_config or registry.get_middleware_config()
    │   → 加载 shell.json: {"workspace_root": "."}
    │
    v
[工厂层] BaseDeepAgentFactory.create_agent(...)        // project_context: ✅ 从 checkpointer 提取
    │
    ├── _inject_skills_middleware(..., project_context) // project_context: ✅ 已传入
    │
    └── _inject_shell_tool(tools, middleware_config)    // project_context: ❌ 未传入！断裂点
            │
            v
        [组件层] build_shell_config({"workspace_root": "."})
            │   workspace_root = Path(".").resolve()
            │   → 解析为进程 CWD = 应用根目录（错误！）
            │
            v
        [组件层] ShellToolMiddleware(config)
            │
            v
        [组件层] PersistentShellSession(workspace=应用根目录)
                subprocess.Popen(cwd="D:\Projects\...\Muti-AI-Agent")  // 错误目录
```

### 2.2 配置加载阶段

配置文件 `config/agents/deep/middleware/shell.json` 中硬编码了：

```json
{ "workspace_root": "." }
```

该值通过以下加载链进入系统：

```
config/agents/deep/middleware/shell.json
    |
    v
DeepAgentsProviderRegistry._load_middleware_config()
    [src/core/providers/deepagents_provider_registry.py]
    调用: config_loader.load_shared_json("agents/deep/middleware/shell.json")
    |
    v
返回 dict: {"workspace_root": ".", "enabled": true, ...}
    |
    v
DeepAgentManager.create_agent()
    [deep_agent_manager.py → create_agent()]
    middleware_cfg = middleware_config or self.provider_registry.get_middleware_config()
    # middleware_config 参数为 None，因此从 registry 加载
    |
    v
BaseDeepAgentFactory.create_agent()
    [base.py → create_agent()]
    resolved_middleware = self._resolve_middleware_config(adapter, middleware_config)
    # shell 配置被原样传递
```

### 2.3 路径解析阶段（问题发生点）

```
BaseDeepAgentFactory._inject_shell_tool()
    [base.py → _inject_shell_tool()]
    |
    v
build_shell_config(shell_config)
    [config.py → build_shell_config()]
    workspace_root = config_dict.get("workspace_root", ".")  # 得到 "."
    workspace_root = Path(".").resolve()
    # 解析为调用时的进程 CWD = D:\Projects\Langchain\Muti-AI-Agent
    |
    v
ShellToolMiddleware(config=config)  # workspace_root 已固化为错误路径
    |
    v
PersistentShellSession(workspace=config.workspace_root)
    subprocess.Popen(cwd=str(self._workspace))  # 在错误目录启动 shell
```

### 2.4 上下文传递链路（断裂位置表）

| 调用层 | 文件 → 函数 | project_context 状态 |
|--------|------------|---------------------|
| 应用层 | agent_lifecycle.py → `create_default_deep_agent(ctx)` | ✅ `ctx.project_context` 可用 |
| 应用层 | agent_lifecycle.py → `_instantiate_agent(ctx, ...)` | ✅ `ctx.project_context` 可用 |
| 管理层 | deep_agent_manager.py → `create_deep_agent(...)` | ✅ 通过 `deep_checkpointer` 携带 |
| 管理层 | deep_agent_manager.py → `create_agent(...)` | ✅ 通过 `deep_checkpointer` 携带 |
| 工厂层 | base.py → `create_agent(...)` | ✅ 从 `deep_checkpointer` 提取 |
| 工厂层 | base.py → `_inject_skills_middleware(...)` | ✅ **已正确传入并使用** |
| 工厂层 | base.py → `_inject_shell_tool(...)` | ❌ **未传入 — 断裂点** |

**根因总结**: `_inject_shell_tool()` 方法签名中缺少 `project_context` 参数。
对比 `_inject_skills_middleware()` 已经正确接收并使用了 `project_context`，
二者在同一层代码中存在**接口不一致** *(违反 Consistency Principle)*。

---

## 3. 代码级问题分析

### 3.1 问题一：配置文件语义模糊

> **违反原则**: *配置即意图 (Configuration as Intent)* — 配置值应清晰表达意图，而非依赖运行时上下文。

`shell.json` 中 `"workspace_root": "."` 存在隐式时序依赖：

- 值 `"."` 本身不携带任何明确语义
- 实际解析结果取决于 `Path(".").resolve()` 被调用时的进程 CWD
- 进程 CWD 与用户项目目录并非同一概念

### 3.2 问题二：工厂层注入不一致

> **违反原则**: *Consistency Principle* — 同层级的方法对相同依赖应保持一致的传递模式。

`BaseDeepAgentFactory.create_agent()` 中，`project_context` 的使用存在不一致：

```python
# create_agent() 中提取 project_context
project_context = user_params.get("project_context")
if project_context is None and deep_checkpointer is not None:
    project_context = getattr(deep_checkpointer, "project_context", None)

# skills 中间件正确使用了 project_context
skills_middleware = self._inject_skills_middleware(
    resolved_middleware,
    filesystem_middlewares,
    project_context=project_context,  # <-- 传入
)

# shell 中间件缺失 project_context
tools, shell_middleware = self._inject_shell_tool(tools, resolved_middleware)
#                                                       ^-- 未传入 project_context
```

### 3.3 问题三：ShellMiddlewareService 未被使用

> **违反原则**: *SRP / No Dead Code* — 代码应有明确职责，孤立代码增加维护负担。

`src/application/services/agent/deep/middleware/shell_service.py` 中的
`ShellMiddlewareService` 类在主流程中从未被实例化或调用。

工厂层直接调用 `build_shell_config()`：

```python
# base.py → _inject_shell_tool()
config = build_shell_config(shell_config)
```

而不经过服务层，导致 `ShellMiddlewareService` 成为孤立代码，
也失去了在服务层融合运行时上下文的机会。

### 3.4 问题四：middleware_config 在 agent_lifecycle 层未被注入

> **违反原则**: *Explicit is Better than Implicit (Python Zen)* — 显式传递优于隐式 fallback。

`_instantiate_agent()` 调用 `create_deep_agent()` 时，
没有传递 `middleware_config` 参数：

```python
# agent_lifecycle.py → _instantiate_agent()
agent = await deep_agent_manager.create_deep_agent(
    provider=resolved_provider,
    model=resolved_model,
    deep_checkpointer=deep_checkpointer,
    function_type=function_type,
    # middleware_config 未传递
)
```

导致 `DeepAgentManager.create_agent()` fallback 到从 registry 加载静态配置：

```python
# deep_agent_manager.py → create_agent()
middleware_cfg = middleware_config or self.provider_registry.get_middleware_config()
```

---

## 4. 官方 deepagents 对比

官方 `LocalShellBackend`（`deepagents/libs/deepagents/deepagents/backends/local_shell.py`）
的设计思路：

- `root_dir` 参数由调用者显式传入
- `root_dir=None` 时才 fallback 到 `Path.cwd()`
- 每次 `execute()` 调用的 `cwd` 都来自初始化时的 `self.cwd`
- 没有 `"auto"` 或 `"."` 之类的间接语义

**设计假设**: 调用者知道并传入正确的工作目录。
我们的实现打破了这个假设——配置文件提供了一个无法正确解析的相对路径。

---

## 5. 影响范围

| 影响项 | 说明 | 严重性 |
|--------|------|--------|
| shell 命令执行目录错误 | 所有 shell 命令在应用根目录执行，而非用户项目目录 | 🔴 高 |
| 相对路径命令失效 | 如 `ls`, `cat file.txt` 等依赖 CWD 的命令结果错误 | 🔴 高 |
| 文件操作风险 | 在错误目录执行写入/删除操作可能影响应用源代码 | 🔴 高 |
| deep agent 工作效率 | agent 需要额外的 `cd` 命令才能到达目标目录 | 🟡 中 |

---

## 6. 涉及文件清单

| 文件 | 架构层 | 角色 | 需修改 |
|------|--------|------|--------|
| `config/agents/deep/middleware/shell.json` | 配置层 | 配置默认值 | 是 |
| `src/components/.../shell/config.py` | 组件层 | ShellConfig 构建 | 是 |
| `src/agents/deepagents/factories/base.py` | 工厂层 | 中间件注入 | 是 |
| `src/application/.../middleware/shell_service.py` | 服务层 | 配置管理 | 是 |
| `src/application/.../agent_lifecycle.py` | 应用层 | agent 生命周期 | 是 |
| `src/agents/.../deep_agent_manager.py` | 管理层 | agent 管理器 | 否 (签名已支持) |
| `src/components/.../shell/middleware.py` | 组件层 | 中间件实现 | 否 |
| `src/components/.../shell/session.py` | 组件层 | shell 会话 | 否 |

---

## 7. 问题总结

本问题的核心可归纳为以下四个子问题的组合作用：

```
[P1] 配置语义模糊        ← "." 不表达意图，依赖进程 CWD
     +
[P2] 上下文传递断裂      ← _inject_shell_tool() 缺少 project_context
     +
[P3] 服务层未被接入      ← ShellMiddlewareService 为孤立代码
     +
[P4] 生命周期层未注入配置 ← middleware_config 未显式传递
     ═══════════════════
     → shell 在错误的目录中执行
```

修复方案见 [design-proposal.md](./design-proposal.md)。
