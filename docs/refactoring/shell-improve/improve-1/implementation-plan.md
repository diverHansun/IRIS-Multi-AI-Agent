# Shell 工作目录优化实施计划

> **文档定位**: 实施步骤文档，定义修改清单、执行约束与验证方案。
>
> **关联文档**:
> [problem-analysis.md](./problem-analysis.md) — 问题诊断（根因链路、代码级分析）
> [design-proposal.md](./design-proposal.md) — 方案设计（配置语义、架构决策、数据流）

---

## 1. 修改文件清单

共 5 个文件，按架构层级排列:

| 序号 | 文件 | 架构层 | 修改类型 | 影响范围 |
|------|------|--------|---------|---------|
| 1 | `config/agents/deep/middleware/shell.json` | 配置层 | 配置变更 | 默认值 |
| 2 | `src/components/.../shell/config.py` | 组件层 | 签名扩展 | 构建函数 |
| 3 | `src/application/.../middleware/shell_service.py` | 服务层 | 功能增强 | 配置融合 |
| 4 | `src/agents/deepagents/factories/base.py` | 工厂层 | 签名扩展 + 调用修改 | 中间件注入 |
| 5 | `src/application/.../agent_lifecycle.py` | 应用层 | 上下文注入 | 生命周期 |

### 1.1 步骤依赖关系

以下是各步骤之间的依赖关系图。步骤 1-3 互相独立，可并行实施；
步骤 4-5 依赖前置步骤的签名/方法变更。

```
步骤 1 (shell.json)      ─┐
                          │
步骤 2 (config.py)        ─┼── 步骤 4 (base.py) ── 完成
                          │        ↑
步骤 3 (shell_service.py) ─┼── 步骤 5 (agent_lifecycle.py) ── 完成
                          │
                          └── 可并行实施
```

**详细依赖关系**:

| 步骤 | 依赖 | 原因 |
|------|------|------|
| 步骤 1 | 无 | 纯配置变更，独立 |
| 步骤 2 | 无 | `build_shell_config()` 签名扩展，新参数有默认值，现有调用方不受影响 |
| 步骤 3 | 无 | 新增 `@staticmethod`，不影响现有类方法 |
| 步骤 4 | 步骤 2 | `_inject_shell_tool()` 内部调用 `build_shell_config(shell_config, project_root=...)` |
| 步骤 5 | 步骤 3 | `_instantiate_agent()` 中调用 `ShellMiddlewareService.resolve_workspace()` |

**推荐执行顺序**: 1 → 2 → 3 → 4 → 5（线性执行最安全，步骤 1-3 也可并行）

---

## 2. 各步骤详细修改

### 步骤一: 修改配置文件默认值

**文件**: `config/agents/deep/middleware/shell.json`

**修改内容**: 将 `workspace_root` 从 `"."` 改为 `"auto"`

```json
{
  "enabled": true,
  "workspace_root": "auto",
  "shell_type": "cmd",
  "command_timeout": 30.0,
  "startup_timeout": 10.0,
  "termination_timeout": 5.0,
  "max_output_lines": 100,
  "max_output_bytes": 1048576,
  "environment": {},
  "startup_commands": []
}
```

**验证门**: 配置文件是合法 JSON，可通过 `json.loads()` 解析且 `workspace_root` 值为 `"auto"`。

---

### 步骤二: 扩展 build_shell_config 签名

**文件**: `src/components/deepagents/runtime_middlewares/shell/config.py`

**修改函数**: `build_shell_config()`

**变更点**:
- 新增可选参数 `project_root: Path | None = None`
- 修改 workspace_root 解析逻辑，支持 `"auto"` 哨兵值

**修改后的函数签名**:
```python
def build_shell_config(
    config_dict: Dict[str, Any],
    project_root: Path | None = None,
) -> ShellConfig:
```

**修改后的 workspace_root 解析逻辑** (替换原第 65-69 行):
```python
workspace_root = config_dict.get("workspace_root", "auto")
if workspace_root == "auto":
    workspace_root = project_root if project_root else Path.cwd()
elif isinstance(workspace_root, str):
    workspace_root = Path(workspace_root).resolve()
elif not isinstance(workspace_root, Path):
    workspace_root = project_root if project_root else Path.cwd()
```

**向后兼容性**:
- `project_root` 默认为 `None`，现有调用方 `build_shell_config(dict)` 无需改动
- `"."` 作为字符串仍走 `Path(".").resolve()` 分支（组件层不做 `"."` → 项目目录的替换，此职责属于服务层 `resolve_workspace()`）

**验证门**:
```python
from src.components.deepagents.runtime_middlewares.shell.config import build_shell_config
from pathlib import Path

# 原有调用保持兼容
config = build_shell_config({"workspace_root": "."})
assert config.workspace_root == Path(".").resolve()

# 新增 auto + project_root 功能
config = build_shell_config({"workspace_root": "auto"}, project_root=Path("/test"))
assert config.workspace_root == Path("/test")

# auto + 无 project_root → 安全降级
config = build_shell_config({"workspace_root": "auto"})
assert config.workspace_root == Path.cwd()
```

---

### 步骤三: 增强 ShellMiddlewareService

**文件**: `src/application/services/agent/deep/middleware/shell_service.py`

**变更点 A**: 新增 `resolve_workspace` 静态方法

**新增内容** (在类末尾添加):

```python
@staticmethod
def resolve_workspace(
    raw_config: Dict[str, Any],
    project_root: "Path | None" = None,
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
    if project_root is None:
        return dict(raw_config)

    workspace = raw_config.get("workspace_root", "auto")
    if workspace in ("auto", "."):
        merged = dict(raw_config)
        merged["workspace_root"] = str(project_root)
        return merged

    return dict(raw_config)
```

**变更点 B**: 需要在文件顶部增加导入

```python
from pathlib import Path
```

**变更点 C**: `__init__` 中默认值同步更新

```python
# 变更前
self.workspace_root = self._config.get("workspace_root", ".")

# 变更后
self.workspace_root = self._config.get("workspace_root", "auto")
```

> 原因: 保持与 `shell.json` 新默认值的语义一致性。虽然 `resolve_workspace()` 是 `@staticmethod`
> 不依赖实例状态，但 `describe()` 和 `get_middleware_config()` 会返回此值，
> 应确保返回的默认值语义正确。

**保留现有功能**: `describe()`, `get_middleware_config()` 不变。

**验证门**:
```python
from pathlib import Path
from src.application.services.agent.deep.middleware.shell_service import ShellMiddlewareService

# auto + project_root → 替换
result = ShellMiddlewareService.resolve_workspace(
    {"workspace_root": "auto", "enabled": True},
    project_root=Path("/project"),
)
assert result["workspace_root"] == "/project"
assert result["enabled"] is True  # 其他字段保留

# "." + project_root → 等同 auto
result = ShellMiddlewareService.resolve_workspace(
    {"workspace_root": ".", "enabled": True},
    project_root=Path("/project"),
)
assert result["workspace_root"] == "/project"

# 显式路径 → 保持原值
result = ShellMiddlewareService.resolve_workspace(
    {"workspace_root": "/custom/path"},
    project_root=Path("/project"),
)
assert result["workspace_root"] == "/custom/path"

# 无 project_root → 原样返回
result = ShellMiddlewareService.resolve_workspace(
    {"workspace_root": "auto"},
    project_root=None,
)
assert result["workspace_root"] == "auto"
```

---

### 步骤四: 工厂层 _inject_shell_tool 签名扩展

**文件**: `src/agents/deepagents/factories/base.py`

**依赖**: 步骤二（需 `build_shell_config` 新签名生效）

**变更点 A**: 修改 `_inject_shell_tool` 方法签名

变更前:
```python
def _inject_shell_tool(self, tools, middleware_config):
```

变更后:
```python
def _inject_shell_tool(self, tools, middleware_config, project_context=None):
```

**变更点 B**: 修改内部 `build_shell_config` 调用

变更前:
```python
config = build_shell_config(shell_config)
```

变更后:
```python
project_root = (
    project_context.project_path if project_context else None
)
config = build_shell_config(shell_config, project_root=project_root)
```

**变更点 C**: 修改 `create_agent` 中对 `_inject_shell_tool` 的调用

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

注意: `project_context` 已在 `create_agent()` 中被提取（通过 `user_params.get("project_context")` 或 `deep_checkpointer`），无需额外操作。

**验证门**: 确认 `_inject_shell_tool` 签名与 `_inject_skills_middleware` 的 `project_context` 传递模式一致 (Consistency Principle)。

---

### 步骤五: agent_lifecycle 层注入 middleware_config

**文件**: `src/application/services/agent/deep/agent_lifecycle.py`

**依赖**: 步骤三（需 `ShellMiddlewareService.resolve_workspace()` 方法存在）

**变更点 A**: 新增导入

在文件顶部导入区域添加:
```python
from src.application.services.agent.deep.middleware.shell_service import (
    ShellMiddlewareService,
)
```

> 注意: `deepagents_provider_registry` 已在文件顶部第 8 行导入，**无需新增**。

**变更点 B**: 修改 `_instantiate_agent` 函数

在现有的 `deep_checkpointer` 构建之后、`create_deep_agent` 调用之前，
增加 middleware_config 的运行时融合逻辑:

变更前:
```python
deep_checkpointer = getattr(ctx, "deep_checkpointer", None) or DeepAgentCheckpointer(
    project_context=getattr(ctx, "project_context", None),
    metadata_manager=getattr(ctx, "metadata_manager", None),
)

agent = await deep_agent_manager.create_deep_agent(
    provider=resolved_provider,
    model=resolved_model,
    deep_checkpointer=deep_checkpointer,
    function_type=function_type,
)
```

变更后:
```python
# 提取 project_context（复用于 checkpointer 和 middleware 融合，避免重复 getattr）
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
- `project_context` 提取后复用两次（DRY），替换原代码中的两处 `getattr(ctx, "project_context", None)`
- `switch_deep_agent()` 函数也调用了 `_instantiate_agent()`，只需修改此一处即可覆盖所有入口

**验证门**: `_instantiate_agent()` 调用 `create_deep_agent()` 时应包含 `middleware_config` 参数。

---

## 3. 不修改的文件（确认清单）

| 文件 | 原因 |
|------|------|
| `deep_agent_manager.py` | `create_agent()` 已有 `middleware_config` 参数；`create_deep_agent()` 通过 `**user_params` 透传 |
| `shell/middleware.py` | 接收 `ShellConfig` 对象，不关心 workspace_root 的来源 *(Dependency Inversion)* |
| `shell/session.py` | 接收 `workspace: Path`，不关心路径的来源 |
| `shell/tool.py` | 工具定义层，无路径逻辑 |
| `shell/__init__.py` | 包导出文件，无需变更 |
| `deepagents_provider_registry.py` | 仅负责加载 JSON 配置，不做路径解析 |
| 其他 middleware service 文件 | 无项目目录依赖，不需要类似修改 |

---

## 4. 测试验证方案

### 4.1 单元测试

**build_shell_config 测试用例**:

| 输入 workspace_root | 输入 project_root | 期望结果 | 测试目的 |
|---------------------|-------------------|---------|---------| 
| `"auto"` | `Path("/project")` | `Path("/project")` | auto 正常解析 |
| `"auto"` | `None` | `Path.cwd()` | auto 安全降级 |
| `"."` | `Path("/project")` | `Path(".").resolve()` | 组件层不替换 "." |
| `"/abs/path"` | `Path("/project")` | `Path("/abs/path")` | 显式路径透传 |
| `"rel/path"` | `Path("/project")` | `Path("rel/path").resolve()` | 相对路径 resolve |
| (缺失) | `Path("/project")` | `Path("/project")` | 默认 "auto" |

**ShellMiddlewareService.resolve_workspace 测试用例**:

| 输入 workspace_root | 输入 project_root | 期望输出 workspace_root | 测试目的 |
|---------------------|-------------------|------------------------|---------|
| `"auto"` | `Path("/project")` | `"/project"` | auto 替换 |
| `"auto"` | `None` | `"auto"` (原样保留) | 无 project_root 安全跳过 |
| `"."` | `Path("/project")` | `"/project"` | "." 等同 auto |
| `"/custom/path"` | `Path("/project")` | `"/custom/path"` (不变) | 显式路径不干预 |
| `"relative/path"` | `Path("/project")` | `"relative/path"` (不变) | 非特殊值不干预 |

### 4.2 集成测试

1. 从非项目目录启动 iris，切换到 deep 模式
2. 执行 shell 命令 `pwd`（Linux）或 `cd`（Windows）
3. 验证输出的目录为 iris 启动目录而非应用源代码目录

### 4.3 回归测试

1. 在 `<project>/.iris/agents/deep/middleware/shell.json` 中设置显式路径
2. 验证显式路径优先于项目目录
3. 删除自定义配置，验证回退到 `"auto"` 默认行为

---

## 5. 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 现有用户配置 `"."` 行为变化 | 低 | 低 | `resolve_workspace()` 将 `"."` 映射到项目目录，这是 bug 修复而非破坏性变更 |
| project_context 为 None | 低 | 低 | 所有路径都有 fallback 到 `Path.cwd()`（防御性编程第二层保障） |
| create_deep_agent 参数透传失败 | 极低 | 高 | `**user_params` 机制已在现有调用中验证可用 |
| 配置缓存未刷新 | 低 | 中 | registry 的 `_middleware_cache` 在 `reload()` 时清除 |
| ShellConfig 直接实例化绕过 build 函数 | 极低 | 中 | `ShellConfig.workspace_root` 默认值为 `Path.cwd`，降级安全 |

---

## 6. 实施检查清单

完成所有步骤后，对照以下检查清单进行最终验证:

- [ ] `shell.json` 中 `workspace_root` 值为 `"auto"`
- [ ] `build_shell_config()` 签名包含 `project_root: Path | None = None`
- [ ] `build_shell_config()` 默认 fallback 从 `"."` 改为 `"auto"`
- [ ] `ShellMiddlewareService.resolve_workspace()` 静态方法存在
- [ ] `ShellMiddlewareService.__init__` 中 `workspace_root` 默认值为 `"auto"`
- [ ] `ShellMiddlewareService` 文件顶部包含 `from pathlib import Path`
- [ ] `_inject_shell_tool()` 签名包含 `project_context=None`
- [ ] `_inject_shell_tool()` 内部调用 `build_shell_config(shell_config, project_root=...)`
- [ ] `create_agent()` 中调用 `_inject_shell_tool()` 时传入 `project_context`
- [ ] `_instantiate_agent()` 中导入 `ShellMiddlewareService`
- [ ] `_instantiate_agent()` 中 `project_context` 提取为局部变量并复用
- [ ] `_instantiate_agent()` 调用 `create_deep_agent()` 时传入 `middleware_config`
- [ ] 所有现有测试通过
- [ ] 新增单元测试覆盖 `build_shell_config` 和 `resolve_workspace` 的边界用例
