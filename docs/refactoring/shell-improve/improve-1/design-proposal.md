# Shell 工作目录优化设计方案

> **文档定位**: 方案设计文档，定义配置语义、架构职责与数据流。
>
> **关联文档**:
> [problem-analysis.md](./problem-analysis.md) — 问题诊断（根因链路、代码级分析）
> [implementation-plan.md](./implementation-plan.md) — 实施步骤（修改清单、测试方案）

---

## 1. 设计目标

1. shell 工具的 `workspace_root` 默认跟随项目目录
2. 用户可在配置文件中显式覆盖 `workspace_root` 为任意路径
3. 消除 `"."` 的隐式时序依赖，引入语义明确的 `"auto"` 哨兵值
4. 对齐 `_inject_shell_tool()` 与 `_inject_skills_middleware()` 的 `project_context` 传递模式
5. 赋予 `ShellMiddlewareService` 明确职责（配置融合），消除死代码

## 2. 设计原则

| 原则 | 应用 |
|------|------|
| **显式优于隐式** *(Explicit over Implicit)* | `"auto"` 明确表达"跟随项目目录"的意图，替代 `"."` 的隐式语义 |
| **单一职责** *(SRP)* | `ShellMiddlewareService` 负责静态配置与运行时上下文的融合 |
| **一致性** *(Consistency)* | shell 与 skills 中间件在工厂层使用相同的 `project_context` 传递模式 |
| **防御性编程** *(Defensive Programming)* | 双层保障机制确保即使某一层被绕过，路径仍能正确解析（详见 §7.1） |
| **配置即意图** *(Configuration as Intent)* | 配置值应清晰表达用户意图，不依赖运行时时序 |
| **配置层级不变** | 用户/项目级 `.iris/` 配置仍可覆盖内置默认值 |

---

## 3. 配置层变更

### 3.1 shell.json 默认值变更

文件: `config/agents/deep/middleware/shell.json`

变更前:
```json
{
  "workspace_root": "."
}
```

变更后:
```json
{
  "workspace_root": "auto"
}
```

### 3.2 workspace_root 语义定义

| 值 | 语义 | 解析行为 |
|----|------|----------|
| `"auto"` | 跟随项目目录 *(推荐默认值)* | 由服务层注入 `project_context.project_path` |
| `"."` | 旧版相对路径 *(已弃用)* | 服务层将其等同 `"auto"` 处理 — 替换为项目目录 |
| `"/absolute/path"` | 显式绝对路径 | 直接使用，不做替换 |
| `"relative/path"` | 相对路径（非 `"."` 且非 `"auto"`） | `Path("relative/path").resolve()` |
| (缺失) | 等同 `"auto"` | 默认值 fallback 为 `"auto"` 行为 |

> **`"."` 的处理说明**: 旧版配置中 `"."` 的原有意图是"当前项目目录"，但由于进程 CWD ≠ 项目目录，
> 实际行为是错误的。本方案将 `"."` 在服务层等同 `"auto"` 处理，这**不是行为破坏，而是 bug 修复**——
> 将 `"."` 的实际行为对齐其原始意图。

### 3.3 config.py 增加 auto 支持

文件: `src/components/deepagents/runtime_middlewares/shell/config.py`

`build_shell_config()` 函数签名增加 `project_root` 参数:

```python
def build_shell_config(
    config_dict: Dict[str, Any],
    project_root: Path | None = None,
) -> ShellConfig:
```

解析逻辑:

```python
workspace_root = config_dict.get("workspace_root", "auto")
if workspace_root == "auto":
    workspace_root = project_root if project_root else Path.cwd()
elif isinstance(workspace_root, str):
    workspace_root = Path(workspace_root).resolve()
elif not isinstance(workspace_root, Path):
    workspace_root = project_root if project_root else Path.cwd()
```

**设计要点**:
- `"auto"` + 有 `project_root` → 使用项目目录
- `"auto"` + 无 `project_root` → fallback 到 `Path.cwd()`（安全降级）
- 显式路径字符串 → 按原有逻辑 resolve
- 函数签名变更为可选参数，现有调用方无需强制修改

---

## 4. 服务层变更

### 4.1 ShellMiddlewareService 职责重定义

文件: `src/application/services/agent/deep/middleware/shell_service.py`

**现状**: 纯配置提取器，无实际使用。

**新职责**: 静态配置与运行时上下文的融合层。

### 4.2 设计决策：resolve_workspace() 的职责归属

> **决策记录**: 将 `resolve_workspace()` 放置在 `ShellMiddlewareService` 中作为 `@staticmethod`。

**考虑过的备选方案**:

| 方案 | 放置位置 | 优点 | 缺点 |
|------|---------|------|------|
| **A (采纳)** | `ShellMiddlewareService` | 服务层是应用层→组件层的桥梁，配置融合是服务层的天然职责；与同目录下其他 middleware service 保持类级封装一致 | 方法不依赖实例状态，`@staticmethod` 与 OOP 类的关程度较弱 |
| B | `config.py` 模块级函数 | 与 `build_shell_config()` 并列，配置逻辑聚合 | 让组件层耦合运行时上下文概念，组件层应保持无状态的纯配置构建 |
| C | `agent_lifecycle.py` 内联 | 调用方就地处理，无需额外方法 | 配置融合逻辑散落在调用方，不可复用，违反 SRP |

**选择方案 A 的核心理由**:

1. **职责对齐**: 服务层 (Application Service Layer) 的核心职责之一是**编排**——将静态配置与运行时上下文融合，再传递给下层组件。`resolve_workspace()` 正是这种编排行为。
2. **层级边界清晰**: 组件层 (`config.py`) 应保持"给什么配置就构建什么对象"的纯函数特性，不应耦合"从哪里获取项目目录"的运行时概念。
3. **可测试性**: `@staticmethod` 使得方法可独立测试，无需实例化 `ShellMiddlewareService`。
4. **一致性**: 同目录下的 `VirtualFilesystemMiddlewareService`、`SubagentsMiddlewareService` 等均以类封装形式组织，`resolve_workspace()` 放在 `ShellMiddlewareService` 中保持结构一致。

### 4.3 resolve_workspace() 接口定义

新增类方法:

```python
@staticmethod
def resolve_workspace(
    raw_config: Dict[str, Any],
    project_root: Path | None = None,
) -> Dict[str, Any]:
    """
    将静态配置中的 workspace_root 与运行时 project_root 融合。

    当 workspace_root 为 "auto" 或 "." 时，替换为实际的项目目录。
    当 workspace_root 为显式路径时，保持原值不变。

    Args:
        raw_config: 从配置文件加载的原始 shell 配置字典
        project_root: 运行时检测到的项目根目录

    Returns:
        融合后的配置字典（不修改原字典）
    """
```

**设计要点**:
- 使用 `@staticmethod`，不依赖实例状态
- 返回新字典，不修改输入（不可变原则 / *Immutability*）
- 保留 `describe()` 和 `get_middleware_config()` 原有功能
- `__init__` 中 `workspace_root` 的默认值应同步从 `"."` 更新为 `"auto"`，保持与 shell.json 的语义一致

### 4.4 与其他中间件服务的一致性

当前 `src/application/services/agent/deep/middleware/` 下的服务类模式：

| 服务类 | 核心职责 | 需改动 | 需要运行时上下文 |
|--------|---------|--------|-----------------|
| `VirtualFilesystemMiddlewareService` | 配置提取 + describe | 否 | 否 |
| `RealFilesystemMiddlewareService` | 配置提取 + describe | 否 | 否 |
| `SubagentsMiddlewareService` | 配置提取 + describe | 否 | 否 |
| `PatchToolCallsService` | 配置提取 + describe | 否 | 否 |
| `ShellMiddlewareService` | 配置提取 + describe + **配置融合** | **是** | **是** |

shell 服务的特殊之处在于：它需要融合文件配置与运行时上下文 (`project_path`)。
其他服务不需要这一步，因为它们的配置不依赖项目目录。
新增 `resolve_workspace()` 是 shell 独有的需求，不构成对其他服务的修改压力。

---

## 5. 工厂层变更

### 5.1 _inject_shell_tool 签名对齐

文件: `src/agents/deepagents/factories/base.py`

变更前:
```python
def _inject_shell_tool(self, tools, middleware_config):
```

变更后:
```python
def _inject_shell_tool(self, tools, middleware_config, project_context=None):
```

内部逻辑变更:

```python
config = build_shell_config(
    shell_config,
    project_root=project_context.project_path if project_context else None,
)
```

### 5.2 create_agent 调用处修改

在 `create_agent()` 方法中，修改调用:

变更前:
```python
tools, shell_middleware = self._inject_shell_tool(tools, resolved_middleware)
```

变更后:
```python
tools, shell_middleware = self._inject_shell_tool(
    tools, resolved_middleware, project_context=project_context
)
```

注意: `project_context` 在 `create_agent()` 中已经被提取，直接传入即可。

---

## 6. 生命周期层变更

### 6.1 agent_lifecycle.py 注入 middleware_config

文件: `src/application/services/agent/deep/agent_lifecycle.py`

在 `_instantiate_agent()` 中，增加 middleware_config 的运行时覆盖:

```python
from src.application.services.agent.deep.middleware.shell_service import (
    ShellMiddlewareService,
)

async def _instantiate_agent(ctx, provider, model, function_type):
    # ... 现有 provider/model 解析代码 ...

    # 提取 project_context（复用于 checkpointer 和 middleware 融合）
    project_context = getattr(ctx, "project_context", None)

    deep_checkpointer = getattr(ctx, "deep_checkpointer", None) or DeepAgentCheckpointer(
        project_context=project_context,
        metadata_manager=getattr(ctx, "metadata_manager", None),
    )

    # 获取 middleware 配置并注入项目工作目录
    middleware_cfg = deepagents_provider_registry.get_middleware_config()
    if project_context is not None:
        shell_raw = middleware_cfg.get("shell", {})
        if isinstance(shell_raw, dict):
            middleware_cfg = {
                **middleware_cfg,
                "shell": ShellMiddlewareService.resolve_workspace(
                    shell_raw, project_root=project_context.project_path
                ),
            }

    agent = await deep_agent_manager.create_deep_agent(
        provider=resolved_provider,
        model=resolved_model,
        deep_checkpointer=deep_checkpointer,
        function_type=function_type,
        middleware_config=middleware_cfg,  # 显式传入
    )
```

**设计要点**:
- 在 agent_lifecycle 层（应用服务层）完成上下文注入
- `project_context` 变量提取后在该函数中复用两次（checkpointer + middleware），消除重复的 `getattr` 调用
- 通过 `middleware_config` 参数显式传递给 manager
- manager 签名已支持该参数（`middleware_config: Optional[dict] = None`）
- `deepagents_provider_registry` 已在文件顶部导入，无需新增 import

### 6.2 create_deep_agent 参数透传确认

`DeepAgentManager.create_deep_agent()` 通过 `**user_params` 透传:

```python
async def create_deep_agent(self, provider, model, function_type, deep_checkpointer, **user_params):
    return await self.create_agent(
        provider=provider,
        model=model,
        function=function_type,
        deep_checkpointer=deep_checkpointer,
        **user_params,  # middleware_config 通过 **user_params 透传
    )
```

`create_agent()` 已有 `middleware_config: Optional[dict] = None`，
通过 `**user_params` 传入的 `middleware_config` 键值将被正确接收。

---

## 7. 数据流全景（修改后）

### 7.1 端到端数据流

```
iris 启动
    |
    v
[捕获层] ProjectContext.from_cwd()
    project_path = Path.cwd().resolve()  // 用户启动目录
    |
    v
ctx.project_context.project_path = "/user/actual/project"
    |
    v
[应用层] _instantiate_agent(ctx, ...)                    [agent_lifecycle.py]
    |
    +-- middleware_cfg = registry.get_middleware_config()
    |       shell: {"workspace_root": "auto", ...}
    |
    +-- [服务层] ShellMiddlewareService.resolve_workspace(shell_cfg, project_root)
    |       "auto" → str(project_context.project_path)          ← 第一层保障
    |       返回: {"workspace_root": "/user/actual/project", ...}
    |
    +-- deep_agent_manager.create_deep_agent(middleware_config=middleware_cfg)
            |
            v
        [管理层] DeepAgentManager.create_agent(middleware_config=middleware_cfg)
            |  middleware_cfg 不为 None，跳过 registry 加载
            v
        [工厂层] BaseDeepAgentFactory.create_agent(middleware_config=middleware_cfg)
            |
            +-- project_context = deep_checkpointer.project_context
            |
            +-- _inject_shell_tool(tools, resolved_middleware, project_context)
                    |
                    v
                [组件层] build_shell_config(shell_config, project_root=project_path)
                    workspace_root 已是绝对路径字符串 → Path(str).resolve()
                    结果仍为正确路径                         ← 第二层保障
                    |
                    v
                ShellToolMiddleware(config)
                    |
                    v
                PersistentShellSession(workspace=project_path)
                    subprocess.Popen(cwd="/user/actual/project")  // 正确!
```

### 7.2 双层保障设计（防御性编程）

> **设计哲学**: 本方案在两个架构层分别设置了 workspace_root 的解析屏障。
> 这是**防御性编程 (Defensive Programming)** 的应用——在系统的关键路径上设置多重验证点，
> 确保即使某一层被绕过或发生异常，下游仍能获得正确结果。

**两层保障的协作关系是串行 pipeline，而非并行独立**:

```
                    ┌─────────────────────────────────────┐
                    │  第一层保障（服务层 — 正常路径）       │
                    │  ShellMiddlewareService              │
                    │  .resolve_workspace()                │
                    │                                     │
                    │  "auto" / "." → 项目目录路径字符串    │
                    │  显式路径 → 保持原值                  │
                    └──────────────┬──────────────────────┘
                                   │  输出已是绝对路径字符串
                                   v
                    ┌─────────────────────────────────────┐
                    │  第二层保障（组件层 — 防御路径）       │
                    │  build_shell_config()                │
                    │                                     │
                    │  "auto" + project_root → 项目目录    │
                    │  "auto" + None → Path.cwd() 安全降级 │
                    │  路径字符串 → Path(str).resolve()     │
                    └─────────────────────────────────────┘
```

**为什么需要第二层保障**:

| 场景 | 第一层状态 | 第二层行为 |
|------|----------|----------|
| **正常流程**: lifecycle 调用 resolve_workspace() | ✅ 已将 `"auto"` 替换为路径字符串 | 收到绝对路径字符串，resolve() 结果正确 |
| **直接调用工厂**: 跳过 lifecycle 层 | ❌ 未执行 resolve | 收到 `"auto"`，通过 `project_root` 参数自行解析 |
| **测试/调试**: 直接构建 ShellConfig | ❌ 未执行 resolve | 收到 `"auto"` + `project_root=None`，安全降级到 `Path.cwd()` |

> **DRY 考量**: 两层保障表面上看似重复，但它们处理的是**不同输入状态**。
> 第一层处理的是 `"auto"` → 路径字符串的语义替换；第二层处理的是路径字符串 → `Path` 对象的构建。
> 二者职责不同，不构成 DRY 违反。

---

## 8. 用户自定义路径的优先级

配置三层覆盖机制不变:

```
(低) config/agents/deep/middleware/shell.json        // 内置默认: "auto"
 |
 v
(中) ~/.iris/agents/deep/middleware/shell.json       // 用户全局覆盖
 |
 v
(高) <project>/.iris/agents/deep/middleware/shell.json  // 项目级覆盖
```

**场景一**: 用户未做任何配置
- 加载内置默认: `"workspace_root": "auto"`
- `resolve_workspace()` 替换为 `project_context.project_path`
- 结果: shell 在项目目录执行

**场景二**: 用户在项目级配置了显式路径
- 加载: `"workspace_root": "/custom/workspace"`
- `resolve_workspace()` 检测到非 `"auto"` 且非 `"."`，保持原值
- `build_shell_config()` 解析为 `Path("/custom/workspace").resolve()`
- 结果: shell 在用户指定目录执行

**场景三**: 用户配置了 `"."` (旧行为)
- 加载: `"workspace_root": "."`
- `resolve_workspace()` 将 `"."` 等同 `"auto"` 处理，替换为 `project_context.project_path`
- 结果: 等同 `"auto"` — 这是 bug 修复，将实际行为对齐原始意图（详见 §3.2 说明）

---

## 9. 向后兼容性分析

| 现有配置值 | 修改前行为 | 修改后行为 | 兼容性 |
|-----------|-----------|-----------|--------|
| `"."` (旧默认) | 解析为进程 CWD（**错误行为**） | 解析为项目目录 | ✅ Bug 修复 |
| `"/abs/path"` | 解析为该绝对路径 | 解析为该绝对路径 | ✅ 完全兼容 |
| `"rel/path"` | 解析为进程CWD下的相对路径 | 解析为进程CWD下的相对路径 | ✅ 完全兼容 |
| (新) `"auto"` | 不存在 | 解析为项目目录 | ✅ 新增功能 |
| (缺失) | fallback 到 `"."` | fallback 到 `"auto"` | ✅ 行为改善 |

> **兼容性声明**: `"."` 的行为变化是**修复性变更**，不是破坏性变更。
> 旧行为（解析为进程 CWD）本身就是不符合用户预期的 bug。
> 新行为（解析为项目目录）对齐了 `"."` 在用户认知中"当前目录"的含义。

---

## 10. 错误处理与边界条件

### 10.1 project_context 不可用

当 `project_context` 为 `None` 时:
- `resolve_workspace("auto", None)` → 保持 `"auto"`
- `build_shell_config({"workspace_root": "auto"}, project_root=None)` → 使用 `Path.cwd()`
- 效果: 安全降级为修改前的行为

### 10.2 project_path 为 None

当 `project_context` 存在但 `project_path` 为 `None` 时:
- `resolve_workspace()` 第二行检查 `project_root is None` → 返回原字典
- 效果: 等同 10.1，安全降级

### 10.3 project_path 不存在

`ShellToolMiddleware.before_agent()` 中已有验证:

```python
if not self.config.workspace_root.exists():
    raise ValueError(f"Shell workspace does not exist: {self.config.workspace_root}")
```

无需额外处理。此验证是组件层自身的前置条件检查 *(Precondition Check)*。

### 10.4 project_path 类型非 Path

若传入的 `project_root` 为字符串类型:
- `resolve_workspace()` 使用 `str(project_root)`，可正确转换
- `build_shell_config()` 中 `"auto"` 分支直接使用 `project_root`，若为字符串则在后续 `ShellConfig(workspace_root=...)` 时需为 `Path` 类型
- **建议**: 在 `build_shell_config()` 中增加 `Path(project_root)` 类型转换保护
