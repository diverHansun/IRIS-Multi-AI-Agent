# Skills 模块实施方案分析 — 代码审计与设计决策

> 基于对 01–04 文档与现有代码的深度对照审计。
> 本文记录所有发现的问题、**最终设计决策**，以及对 01/03/04 文档的修订指引。
> **状态**：v2 — 已完成第二轮审计与决策（2026-02-13）

---

## 1. 代码架构审计结论

### 1.1 实际调用链（已验证）

```
DeepAgentManager.create_agent()
  # src/agents/deepagents/managers/deep_agent_manager.py
  → DeepAgentFactoryRegistry.get_factory()
  # src/agents/deepagents/factories/registry.py
  → factory.create_agent()
  # src/agents/deepagents/factories/base.py (BaseDeepAgentFactory)
    → _resolve_middleware_config()         # 合并 adapter + 全局中间件配置
    → _inject_filesystem_tools()           # 构建 filesystem_middlewares
    → _inject_shell_tool()                 # 构建 shell_middleware
    → create_deep_agent_runtime()          # src/components/deepagents/runtime.py
```

**结论**：`BaseDeepAgentFactory` 存在且功能完整。03 文档中的 Factory 集成方案**基本正确**。
原 05 v1 中"Factory 不存在"的判断为**误判**，已修正。

### 1.2 Runtime 中间件管线（实际顺序）

```python
# src/components/deepagents/runtime.py — 实际管线构建顺序
deepagent_middleware = [
    ExecutionTimeoutMiddleware(),     # 条件：max_execution_time > 0
    JsonArgsParserMiddleware(),
    TodoListMiddleware(),
    *filesystem_middlewares,          # VirtualFilesystem + RealFilesystem（由工厂注入）
    shell_middleware,                 # 由工厂注入
    SubAgentMiddleware(),
    SummarizationMiddleware(),
    PatchToolCallsMiddleware(),
    HumanInTheLoopMiddleware(),       # 条件：存在 interrupt_on
    *extra_middleware,                # 额外中间件
]
```

**Skills 中间件插入位置**：在 TodoList 之后、Filesystem 之前（与文档设计一致）。

### 1.3 配置加载实际路径

```python
# src/core/providers/deepagents_provider_registry.py — _load_middleware_config()
# 当前只加载 filesystem 和 shell：
return {
    "filesystem": {"virtual": virtual_cfg, "real": real_cfg},
    "shell": shell_cfg,
}
```

`ConfigLoader.load_shared_json()` 使用三层优先级：
1. 项目级 `<project>/.iris/<relative_path>`
2. 用户级 `~/.iris/<relative_path>`
3. 内置 `config/<relative_path>`

### 1.4 现有中间件模块列表

| 模块 | 位置 | 提供工具 |
|------|------|---------|
| `PatchToolCallsMiddleware` | `runtime_middlewares/__init__.py` | 否 |
| `JsonArgsParserMiddleware` | `runtime_middlewares/json_args_parser.py` | 否 |
| `ExecutionTimeoutMiddleware` | `runtime_middlewares/timeout.py` | 否 |
| `RealFilesystemMiddleware` | `runtime_middlewares/real_filesystem/` | 是 |
| `VirtualFilesystemMiddleware` | `runtime_middlewares/virtual_filesystem/` | 是 |
| `ShellToolMiddleware` | `runtime_middlewares/shell/` | 是 |
| `SubAgentMiddleware` | `runtime_middlewares/subagents/` | 否 |

**Skills 中间件特征**：不提供工具，只做 system prompt 注入。

### 1.5 关键类型发现：`allowed_paths` 是不可变 tuple

```python
# src/components/deepagents/runtime_middlewares/real_filesystem/config.py
@dataclass(slots=True)
class RealFilesystemSecurityOptions:
    allowed_paths: tuple[Path, ...]      # ← 不可变 tuple，不可 append
    excluded_paths: tuple[Path, ...]     # ← 同样 tuple
    allowed_extensions: tuple[str, ...]
    max_file_size: int
```

`_prepare_allowed_paths()` 返回 `tuple(unique)`。03 文档中写的 `.append(path)` 会导致 `AttributeError`。

**安全校验共用**：`validate_file()`（读）和 `validate_new_file_path()`（写）都通过 `ensure_directory_access()` → `_is_within(allowed_paths)` 校验。白名单 skill 目录后，agent 可对其执行 read **和** write。

### 1.6 Factory 模式

```
src/agents/deepagents/factories/
├── __init__.py
├── base.py              # BaseDeepAgentFactory（核心抽象工厂）
├── registry.py          # DeepAgentFactoryRegistry
├── coding_factory.py    # CodingFactory
├── research_factory.py  # ResearchFactory
├── analysis_factory.py  # AnalysisFactory
```

`BaseDeepAgentFactory.create_agent()` 完成以下工作：
1. `_resolve_middleware_config()` — 合并 adapter 级和全局级中间件配置
2. 构建 subagent specs
3. 获取 tools
4. `_inject_filesystem_tools()` — 构建 filesystem_middlewares
5. `_inject_shell_tool()` — 构建 shell_middleware
6. 构建 agent 实例
7. 调用 `create_deep_agent_runtime(...)` 创建 runtime

**Skills 注入点**：步骤 4-5 之间添加 `_inject_skills_middleware()`。

### 1.7 命令系统

- `BaseCommand` 在 `src/application/commands/base.py`
- 命令注册在 `src/application/commands/__init__.py` 的 `register_default_commands()`
- 帮助文本在 `src/application/cli/gui/render.py` 中硬编码（元组列表）
- 所有命令使用 `/` 前缀（如 `/help`, `/mcp status`, `/tools list`）

### 1.8 Project 模块

- `IrisShareDir`（`src/core/project/share.py`）：全局 `~/.iris/` 管理器
  - 已有：`get_tools_dir()`, `get_mcp_dir()`, `get_agents_dir()` 等
  - 缺少：`get_skills_dir()` — Phase 1 扩展

- `ProjectContext`（`src/core/project/context.py`）：项目级 `.iris/` 管理器
  - 已有：`iris_dir`, `config_file`, `agent_md_file` 等属性
  - 缺少：`skills_dir` 属性 — Phase 1 扩展

---

## 2. 关键问题与设计决策（Round 2 新增）

### 问题 A：白名单扩展 `.append()` 失败

**根因**：`RealFilesystemSecurityOptions.allowed_paths` 和 `excluded_paths` 都是 `tuple[Path, ...]`（`@dataclass(slots=True)`），不可 append。03 文档中 `mw.options.security.allowed_paths.append(path)` 必然抛 `AttributeError`。

**决策 A**：使用 tuple 重建替代 append。

```python
existing = mw.options.security.allowed_paths
new_paths = tuple(p for p in skill_source_paths if p.exists() and p not in existing)
mw.options.security.allowed_paths = existing + new_paths
```

### 问题 B：read 与 write 共用 `allowed_paths` — 安全风险

**根因**：`validate_file()`（read）和 `validate_new_file_path()`（write）都走 `ensure_directory_access()` → `_is_within(allowed_paths)`。白名单 skill 目录后，agent 可对其执行 `write_real_file` / `edit_real_file`。

**决策 B**：Phase 2 中将 `BUILT_IN_SKILLS_DIR` 加入 `excluded_paths`（写保护）。user/project skill 目录允许 read+write（合理：用户可借助 agent 编辑自己的 skill）。

```python
# 同时保护 built-in 目录
from src.components.shared.skills.types import BUILT_IN_SKILLS_DIR

if BUILT_IN_SKILLS_DIR.exists():
    existing_excluded = mw.options.security.excluded_paths
    if BUILT_IN_SKILLS_DIR not in existing_excluded:
        mw.options.security.excluded_paths = existing_excluded + (BUILT_IN_SKILLS_DIR,)
```

**影响表**：

| Skill 来源 | read (read_real_file) | write (write_real_file) |
|-----------|-----------------------|------------------------|
| built-in | ✅ allowed（allowed_paths） | ❌ blocked（excluded_paths） |
| user (~/.iris/skills/) | ✅ allowed | ✅ allowed |
| project (.iris/skills/) | ✅ allowed | ✅ allowed |

### 问题 C：Factory 阶段 vs before_agent 阶段的时序问题

**根因**：03 文档让 Factory 在创建阶段调用 `skills_middleware.get_skill_source_paths()` 来扩展白名单，但此时 `before_agent()` 尚未执行，路径列表为空。

**决策 C**：Factory 通过 `SkillRegistry.resolve_sources()` 直接计算路径，不依赖 middleware 的 `before_agent()`。

```python
# BaseDeepAgentFactory._inject_skills_middleware()
def _inject_skills_middleware(self, middleware_config, filesystem_middlewares, project_context=None):
    skills_config = middleware_config.get("skills", {})
    if not isinstance(skills_config, dict) or not skills_config.get("enabled", True):
        return None

    from src.components.shared.skills import SkillRegistry
    from src.components.deepagents.runtime_middlewares.skills import SkillsMiddleware

    # 1. 通过公共方法直接计算 source 路径（不依赖 before_agent）
    project_skills_dir = project_context.skills_dir if project_context else None
    sources = SkillRegistry.resolve_sources(
        config=skills_config,
        project_skills_dir=project_skills_dir,
    )
    skill_source_paths = [s.path for s in sources if s.path.exists()]

    # 2. 扩展 RealFilesystem 白名单（tuple 重建 + built-in 写保护）
    self._extend_filesystem_for_skills(skill_source_paths, filesystem_middlewares)

    # 3. 创建 middleware（传入 sources 避免重复计算）
    skills_middleware = SkillsMiddleware(config=skills_config, sources=sources)
    return skills_middleware
```

### 问题 D：CLI 与 Middleware 的 source 解析逻辑重复

**根因**：CLI 的 `_ensure_initialized()` 和 Middleware 的 `_resolve_sources()` 各自独立计算 sources，两套逻辑容易漂移。

**决策 D**：在 `SkillRegistry` 中提供 `resolve_sources()` 公共静态方法，CLI 和 Middleware 共用。

```python
class SkillRegistry:

    @staticmethod
    def resolve_sources(
        *,
        config: Dict[str, Any] | None = None,
        project_skills_dir: Path | None = None,
    ) -> List[SkillSource]:
        """
        统一的 source 解析——CLI 与 Middleware 共用。

        Args:
            config: skills 配置 dict（含 sources.built_in/user/project 开关）
            project_skills_dir: 项目级 skills 目录（可选，无 project 时传 None）

        Returns:
            按 priority 排列的 SkillSource 列表
        """
        from .types import BUILT_IN_SKILLS_DIR, SkillSource, SkillSourceType
        from src.core.project.share import IrisShareDir

        cfg = config or {}
        sources_cfg = cfg.get("sources", {})
        sources: List[SkillSource] = []

        if sources_cfg.get("built_in", True) and BUILT_IN_SKILLS_DIR.is_dir():
            sources.append(SkillSource(
                type=SkillSourceType.BUILT_IN,
                path=BUILT_IN_SKILLS_DIR,
                priority=0,
            ))

        if sources_cfg.get("user", True):
            sources.append(SkillSource(
                type=SkillSourceType.USER,
                path=IrisShareDir.get_skills_dir(),
                priority=1,
            ))

        if sources_cfg.get("project", True) and project_skills_dir and project_skills_dir.is_dir():
            sources.append(SkillSource(
                type=SkillSourceType.PROJECT,
                path=project_skills_dir,
                priority=2,
            ))

        return sources
```

CLI 端：
```python
# SkillsCommand._ensure_initialized()
sources = SkillRegistry.resolve_sources(
    config=skills_config,
    project_skills_dir=getattr(ctx, "project_context", None) and ctx.project_context.skills_dir,
)
registry.initialize(sources)
```

### 问题 E：Source 指纹检查

**决策 E**：推迟到 Phase 4（`/skills reload` 的实现基础）。Phase 1 的 Registry 初始化一次后在整个 session 生命周期内不变。

---

## 3. 完整决策清单（Round 1 + Round 2）

| # | 决策项 | 内容 | Round |
|---|--------|------|-------|
| 1 | 集成入口 | 在 `BaseDeepAgentFactory` 中添加 `_inject_skills_middleware()` | R1 |
| 2 | 中间件注入 | `runtime.py` 新增 `skills_middleware` 参数，TodoList 之后、Filesystem 之前 | R1 |
| 3 | 白名单策略 | 源根白名单（三个 source root 目录） | R1 |
| 4 | SkillLoadError | 保留原字段 + `@property path/message` 桥接 | R1 |
| 5 | SkillMetadata | 保留 `path`（SKILL.md 路径），CLI 用 `skill.path.parent` | R1 |
| 6 | Registry API | 增加 `is_initialized()` 公开方法 | R1 |
| 7 | Formatter | 接受 `max_skills: int = 20` 参数，支持截断 | R1 |
| 8 | BUILT_IN_DIR | `types.py` 中集中定义 `BUILT_IN_SKILLS_DIR` 常量 | R1 |
| 9 | Phase 范围 | Phase 3: list/create/info；validate/reload 移至 Phase 4 | R1 |
| 10 | 配置加载 | `_load_middleware_config()` 增加 `"skills"` 键 | R1 |
| 11 | ensure_structure | 不自动创建 skills 目录，只在 `/skills create --project` 时创建 | R1 |
| A | tuple 重建 | `allowed_paths = existing + new_paths` 替代 `.append()` | R2 |
| B | 写保护 | `BUILT_IN_SKILLS_DIR` 加入 `excluded_paths`；user/project 允许 read+write | R2 |
| C | Factory 直算路径 | 通过 `resolve_sources()` 直接计算，不依赖 `before_agent()` | R2 |
| D | 统一 resolve_sources | `SkillRegistry.resolve_sources()` 公共方法，CLI 与 Middleware 共用 | R2 |
| E | source 指纹 | 推迟到 Phase 4 | R2 |

---

## 4. 文档修订指引

### 4.1 对 01-architecture.md 的修订

| 节 | 修改内容 |
|----|---------|
| §4.1 Constants | 增加 `BUILT_IN_SKILLS_DIR` 常量 |
| §5.2 SkillRegistry | 增加 `is_initialized()` 方法；增加 `resolve_sources()` 静态方法 |
| §5.3 SkillsMiddleware | 方法名 → `get_skill_source_paths()`；收集三个源根路径 |
| §5.3 SkillsMiddleware | 构造函数接受 `sources` 参数，避免重复计算 |
| §5.4 Security | 说明 `allowed_paths` 是 tuple，需重建；built-in 加入 `excluded_paths` |
| §6.1 Formatter | `format()` 签名增加 `max_skills` 参数 |
| §7.2 ProjectContext | `ensure_structure()` 不创建 skills 目录 |
| §8.3 SkillLoadError | 增加 `@property path/message` |
| §8.x （新增） | 日志级别约定表 |
| §13 Phases | Phase 3 移除 validate/reload → Phase 4；Phase 4 增加 source 指纹 |
| §8.3 Error Reporting | `cli.py skills validate --all` 标注 `(Phase 4)` |

### 4.2 对 03-integration-guide.md 的修订

| 节 | 修改内容 |
|----|---------|
| §2.2 ProjectContext | 标题改为"声明 skills_dir 属性"，删除 "Update ensure_structure" 误导 |
| §3.2 Factory | `_extend_filesystem_for_skills()` 使用 tuple 重建；增加 built-in `excluded_paths` |
| §3.2 Factory | `_inject_skills_middleware()` 使用 `resolve_sources()` 直接计算路径 |
| §3.3 Runtime | `skills_middleware` 参数注入 |
| §4 Security | 说明 read/write 共用 allowed_paths；built-in 写保护方案 |
| §5 Config | `_load_middleware_config()` 增加 skills |
| §new Source Resolution | 增加 "统一 source 解析" 节 |

### 4.3 对 04-cli-commands.md 的修订

| 节 | 修改内容 |
|----|---------|
| `_ensure_initialized` | 使用 `SkillRegistry.resolve_sources()` 替换硬编码逻辑 |
| `_format_skill_info` | `skill.path.parent`（已完成） |
| Future Extensions | 标注 Phase 4（已完成） |

---

## 5. 实施顺序（最终版）

```
Phase 1 — 共享基础设施
  1.1 types.py            数据模型 + BUILT_IN_SKILLS_DIR
  1.2 validator.py         名称 + 元数据校验
  1.3 loader.py            SKILL.md 发现与解析
  1.4 registry.py          单例 + 缓存 + is_initialized() + resolve_sources()
  1.5 formatter.py         系统提示格式化 + max_skills
  1.6 __init__.py          公共 API 导出
  1.7 share.py 扩展        IrisShareDir.get_skills_dir()
  1.8 context.py 扩展      ProjectContext.skills_dir（不自动创建）
  1.9 skills.json 配置     config/agents/deep/middleware/skills/

Phase 2 — Deep Agent 集成
  2.1 SkillsMiddleware              runtime_middlewares/skills/
  2.2 _inject_skills_middleware()   BaseDeepAgentFactory（使用 resolve_sources）
  2.3 _extend_filesystem_for_skills()  tuple 重建 + built-in 写保护
  2.4 runtime.py 签名               新增 skills_middleware 参数
  2.5 _load_middleware_config()      增加 skills 键
  2.6 _resolve_middleware_config()   增加 "skills" 遍历键
  2.7 skill-creator SKILL.md        内置元技能

Phase 3 — CLI 命令
  3.1 SkillsCommand           /skills list, /skills create, /skills info
  3.2 命令注册                 __init__.py（使用 resolve_sources）
  3.3 帮助系统                 render.py SKILL_COMMANDS

Phase 4 — 高级特性
  4.1 /skills validate
  4.2 /skills reload（含 source 指纹检查）
  4.3 context: fork 支持
  4.4 allowed-tools 强制执行
  4.5 Basic mode 集成
```

---

## 6. 遗留问题与后续跟踪

### 6.1 测试夹具约定

`tests/fixtures/skills/` 下的 fixture 目录名必须满足 `SKILL_NAME_PATTERN` 且与 frontmatter 的 `name` 字段一致。

### 6.2 日志级别约定

| 场景 | 级别 | 结构化字段 |
|------|------|-----------|
| Skill 成功加载 | `logger.debug` | `skill_name`, `source_type` |
| Skill 被更高优先级覆盖 | `logger.warning` | `skill_name`, `old_source`, `new_source` |
| YAML 解析失败 | `logger.warning` | `path`, `error` |
| 必填字段缺失 | `logger.warning` | `skill_name`, `field` |
| 源目录不可访问 | `logger.error` | `source_path`, `error` |
| Registry 初始化完成 | `logger.info` | `skill_count`, `error_count` |

### 6.3 Source 解析与项目上下文

- 有 project 时：三个 source（built-in + user + project）
- 无 project 或 `sources.project: false` 时：只使用 built-in + user
- CLI 与 Middleware 共用 `SkillRegistry.resolve_sources()`，保证 source 列表一致

### 6.4 Phase 4 预留：Source 指纹检查

当实现 `/skills reload` 时，可在 `SkillRegistry` 中增加 source 目录的修改时间戳指纹检查，source 变化时自动 re-init，避免手动 reload。
