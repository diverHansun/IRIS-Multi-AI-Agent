# 实施计划与变更清单

## 1. 实施顺序

三个改进项之间存在依赖关系:

```
G3 模板简化 (独立, 无依赖)
     |
     | 可并行
     v
G2 脚本路径引导
     |
     | G2 中 types.py 变更是 G1 测试的前提
     v
G1 reload 命令
```

推荐实施顺序:

1. **Step 1**: G3 模板简化 -- 独立变更, 改动最小, 可先完成
2. **Step 2**: G2 数据层 -- types.py 增加 SkillResources, loader.py 增加扫描
3. **Step 3**: G2 展示层 -- formatter.py 输出扩展
4. **Step 4**: G1 reload -- 命令层变更
5. **Step 5**: 测试与验证

## 2. 详细变更清单

### Step 1: 模板简化 (G3)

**文件**: `src/application/commands/shared/skills_commands.py`

**变更**: 替换 `_skill_template()` 方法体

**修改前**:

```python
@staticmethod
def _skill_template(name: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "description: >\n"
        "  TODO: Describe what this skill does and when to use it.\n"
        "  Include keywords that help the agent recognize relevant tasks.\n"
        "metadata:\n"
        '  author: ""\n'
        '  version: "1.0.0"\n'
        "  category: general\n"
        "---\n"
        "\n"
        f"# {name}\n"
        "\n"
        "TODO: Add skill instructions here.\n"
        "\n"
        "## When to Use\n"
        "\n"
        "Describe the scenarios where this skill should be activated.\n"
        "\n"
        "## Workflow\n"
        "\n"
        "### Step 1: ...\n"
        "\n"
        "### Step 2: ...\n"
        "\n"
        "## Edge Cases\n"
        "\n"
        "- TODO: Document edge cases\n"
    )
```

**修改后**:

```python
@staticmethod
def _skill_template(name: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "description: >\n"
        "  TODO: Describe what this skill does and when to use it.\n"
        "  Include both what the skill does and specific triggers for when to use it.\n"
        "---\n"
        "\n"
        f"# {name}\n"
        "\n"
        "TODO: Add skill instructions here.\n"
        "\n"
        "## Workflow\n"
        "\n"
        "### Step 1: ...\n"
        "\n"
        "### Step 2: ...\n"
        "\n"
        "## Edge Cases\n"
        "\n"
        "- TODO: Document edge cases and fallback behavior\n"
    )
```

### Step 2: 数据层扩展 (G2 - 数据)

**文件 1**: `src/components/shared/skills/types.py`

**变更**: 在 `SkillLoadError` 类之前增加 `SkillResources` 数据类,
在 `SkillMetadata` 中增加 `resources` 字段。

**新增代码** (插入位置: `SkillMetadata` 类定义之后、`SkillLoadError` 类之前):

```python
@dataclass
class SkillResources:
    """Discovered sub-resources within a skill directory."""

    scripts: List[Path] = field(default_factory=list)
    references: List[Path] = field(default_factory=list)
    assets: List[Path] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        """Return True if any resource type has entries."""
        return bool(self.scripts or self.references or self.assets)
```

**SkillMetadata 修改**: 在内部字段区域增加:

```python
resources: "SkillResources" = field(default_factory=lambda: SkillResources())
```

注: 使用字符串引用避免前向引用问题, 或调整类定义顺序使 `SkillResources` 在 `SkillMetadata` 之前。
推荐调整定义顺序: `SkillResources` 放在 `SkillMetadata` 之前。

---

**文件 2**: `src/components/shared/skills/loader.py`

**变更**: 增加 `_scan_resources` 方法, 在 `load_from_source` 中加载完 skill 后调用。

**新增方法**:

```python
_RESOURCE_DIRS = ("scripts", "references", "assets")

def _scan_resources(self, skill_dir: Path) -> "SkillResources":
    """Scan standard sub-directories for bundled resource files."""
    from .types import SkillResources

    resources = SkillResources()
    for subdir_name in _RESOURCE_DIRS:
        subdir = skill_dir / subdir_name
        if not subdir.is_dir():
            continue
        files = sorted(
            f for f in subdir.iterdir()
            if f.is_file() and not f.name.startswith(".")
        )
        setattr(resources, subdir_name, files)
    return resources
```

**调用位置**: 在 `load_from_source` 方法中, `skill.source_type = source.type` 之前:

```python
skill.resources = self._scan_resources(skill_dir)
```

---

**文件 3**: `src/components/shared/skills/__init__.py`

**变更**: 导出列表增加 `SkillResources`。

### Step 3: 展示层扩展 (G2 - 展示)

**文件**: `src/components/shared/skills/formatter.py`

**变更**: 修改 `format()` 方法, 为有资源的 skill 输出额外的 Scripts/References 行,
并更新尾部引导文本。

**修改后的 format 方法**:

```python
def format(self, skills: List[SkillMetadata], max_skills: int = 20) -> str:
    if not skills:
        return ""

    display_skills = skills[:max_skills]
    has_any_scripts = False
    lines = ["## Available Skills", ""]
    lines.append(
        "You have access to specialized skills. "
        "To activate a skill, use read_real_file to read its SKILL.md."
    )
    lines.append("")

    for skill in display_skills:
        lines.append(f"- {skill.name}: {skill.description}")
        lines.append(f"  Path: {skill.path}")

        if hasattr(skill, "resources") and skill.resources.has_content:
            skill_dir = skill.path.parent
            if skill.resources.scripts:
                script_names = ", ".join(
                    str(f.relative_to(skill_dir)) for f in skill.resources.scripts
                )
                lines.append(f"  Scripts: {script_names}")
                has_any_scripts = True
            if skill.resources.references:
                ref_names = ", ".join(
                    str(f.relative_to(skill_dir)) for f in skill.resources.references
                )
                lines.append(f"  References: {ref_names}")

    if len(skills) > max_skills:
        lines.append(f"\n(showing {max_skills} of {len(skills)} skills)")

    lines.append("")
    lines.append(
        "Only read a skill's SKILL.md when the user's task "
        "matches the skill's description."
    )
    if has_any_scripts:
        lines.append(
            "When a skill has Scripts listed, you can execute them "
            "using the shell tool. Run scripts by their full path "
            "derived from the skill's Path prefix."
        )
    return "\n".join(lines)
```

### Step 4: reload 命令 (G1)

**文件**: `src/application/commands/shared/skills_commands.py`

**变更 1**: 在 `execute` 方法的 `handlers` 字典中增加 reload 入口。

```python
handlers = {
    "list": self._handle_list,
    "create": self._handle_create,
    "info": self._handle_info,
    "reload": self._handle_reload,
}
```

**变更 2**: 增加 `_handle_reload` 方法。

```python
async def _handle_reload(self, ctx, args: list[str]) -> CommandResult:  # noqa: ARG002
    try:
        from src.components.shared.skills import SkillRegistry

        registry = SkillRegistry.get_instance()
        if not registry.is_initialized():
            self._ensure_initialized(registry, ctx)
        else:
            registry.reload()

        skills = registry.get_all_skills()
        errors = registry.get_load_errors()

        summary = f"Skills reloaded.\n  Loaded: {len(skills)} skill(s)"
        if errors:
            summary += f"\n  Errors: {len(errors)}"
            summary += "\n\n  Warnings:"
            for err in errors:
                summary += f"\n    [WARN] {err.path}: {err.message}"
        return CommandResult.success(summary)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Failed to reload skills: %s", exc, exc_info=True)
        return CommandResult.error(f"Failed to reload skills: {exc}")
```

**变更 3**: 更新 `_usage()` 帮助文本。

```python
def _usage(self) -> str:
    return (
        "Usage:\n"
        "  /skills list\n"
        "  /skills create <name> [--project]\n"
        "  /skills info <name>\n"
        "  /skills reload"
    )
```

### Step 5: 测试

**新增测试文件**: `tests/unit/components/shared/skills/test_skills_reload_and_resources.py`

测试用例清单:

```
TestSkillReloadCommand:
    test_reload_success             - 正常 reload 返回统计
    test_reload_uninitialized       - 未初始化时等同于首次加载
    test_reload_with_errors         - 有加载错误时的输出格式
    test_reload_exception_handling  - 异常处理

TestSkillResources:
    test_scan_resources_with_scripts     - 有 scripts/ 子目录
    test_scan_resources_empty            - 无子目录
    test_scan_resources_hidden_files     - 过滤隐藏文件
    test_scan_resources_mixed            - scripts + references + assets
    test_scan_resources_nonexistent_dir  - skill 目录不存在

TestFormatterWithResources:
    test_format_with_scripts        - 输出包含 Scripts 行
    test_format_without_resources   - 无 resources 时不显示额外行
    test_format_with_references     - 输出包含 References 行
    test_format_shell_guidance      - 有 scripts 时输出执行指引

TestTemplateSimplification:
    test_template_no_metadata       - 不含 metadata 块
    test_template_no_category       - 不含 category
    test_template_has_name_desc     - 包含 name 和 description
    test_template_no_when_to_use    - 不含 When to Use 小节
```

## 3. 文件变更汇总

| 文件 | 操作 | 变更行数(估) |
|------|------|-------------|
| `src/components/shared/skills/types.py` | 修改 | +20 |
| `src/components/shared/skills/loader.py` | 修改 | +20 |
| `src/components/shared/skills/formatter.py` | 修改 | +25 |
| `src/components/shared/skills/__init__.py` | 修改 | +1 |
| `src/application/commands/shared/skills_commands.py` | 修改 | +30, -15 |
| `tests/unit/components/shared/skills/test_skills_reload_and_resources.py` | 新增 | +150 |
| **合计** | | ~260 行 |

## 4. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| `_scan_resources` 扫描大量文件导致加载变慢 | 低 | 低 | 仅扫描一层、三个固定目录名, 日常 skill 文件数量有限 |
| `resources` 字段默认值导致序列化问题 | 低 | 中 | 使用 `field(default_factory=...)`, 与现有字段模式一致 |
| 旧版 SKILL.md 包含 metadata 字段后解析异常 | 无 | 无 | loader 对未知字段容错, 不会因多出字段而失败 |

## 5. 回滚方案

所有变更均为追加式修改或独立替换:
- G1 的 reload 命令可通过移除 handler 字典条目和方法独立回滚
- G2 的 resources 扫描可通过移除 _scan_resources 调用回滚, formatter 恢复原逻辑
- G3 的模板替换可独立还原

三项变更之间无循环依赖, 支持独立回滚。
