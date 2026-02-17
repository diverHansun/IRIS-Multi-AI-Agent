# 技术方案设计

## 1. 架构概览

本轮改进不引入新的组件层, 仅在现有架构内进行扩展:

```
SkillsCommand (CLI)                  SkillPromptFormatter (Prompt)
     |                                        |
     | +reload 子命令                          | +脚本路径信息
     v                                        v
SkillRegistry (单例)                  SkillMetadata (数据)
     |                                        |
     | .reload() 已存在                        | +resources 字段
     v                                        v
SkillLoader (扫描)                    SkillLoader (扫描)
                                              |
                                              | +扫描子目录
                                              v
                                     scripts/, references/
```

核心设计决策: **skills 系统只提供信息, 不控制执行**。
脚本路径通过 formatter 写入 system prompt, agent 自主决定是否通过 shell 工具执行。
这保持了 skills 中间件与 shell 中间件的职责分离。

## 2. 改进项 G1: /skills reload 命令

### 2.1 设计方案

在 `SkillsCommand` 的 `handlers` 字典中增加 `"reload"` 键, 映射到 `_handle_reload` 方法。

**处理逻辑**:

```
1. 获取 SkillRegistry 单例
2. 如果 registry 未初始化 -> 执行 _ensure_initialized (首次加载)
3. 如果 registry 已初始化 -> 调用 registry.reload() (重新扫描)
4. 收集 reload 后的统计信息
5. 返回格式化的结果
```

**边界情况**:
- registry 未初始化时, reload 等同于首次加载, 需要先解析 sources
- reload 过程中某个 source 目录不可访问, 应记录错误但不中断其他 source 的加载
  (该行为已由 `SkillRegistry._load_all()` 保证)

### 2.2 接口设计

**命令格式**: `/skills reload`

**输出格式**:

```
Skills reloaded.
  Loaded: 5 skill(s) from 3 source(s)
  Errors: 1

  Warnings:
    [WARN] /path/to/broken-skill/SKILL.md: missing YAML frontmatter
```

### 2.3 变更范围

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/application/commands/shared/skills_commands.py` | 修改 | 增加 `_handle_reload` 方法, 更新 handlers 字典, 更新 `_usage()` 帮助文本 |

变更量: 约 25 行。

## 3. 改进项 G2: 脚本路径引导

### 3.1 设计方案

采用两层变更:

**第一层 - 数据层**: 在 `SkillMetadata` 中增加 `resources` 字段, 记录 skill 目录下的子资源文件。
在 `SkillLoader` 的加载过程中扫描 `scripts/` 和 `references/` 子目录, 将发现的文件路径写入该字段。

**第二层 - 展示层**: 在 `SkillPromptFormatter.format()` 的输出中, 为有 scripts 或 references 
的 skill 追加对应的路径信息, 引导 agent 知道这些资源的存在。

### 3.2 数据模型扩展

在 `types.py` 中增加 `SkillResources` 数据类:

```python
@dataclass
class SkillResources:
    """Discovered sub-resources within a skill directory."""
    scripts: List[Path] = field(default_factory=list)
    references: List[Path] = field(default_factory=list)
    assets: List[Path] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        return bool(self.scripts or self.references or self.assets)
```

在 `SkillMetadata` 中新增字段:

```python
resources: SkillResources = field(default_factory=SkillResources)
```

### 3.3 加载器扩展

在 `SkillLoader.load_from_source()` 中, 解析完 SKILL.md 后, 扫描 skill 目录下的
标准子目录:

```python
RESOURCE_DIRS = ("scripts", "references", "assets")

def _scan_resources(self, skill_dir: Path) -> SkillResources:
    """Scan standard sub-directories within a skill directory."""
    resources = SkillResources()
    for subdir_name in RESOURCE_DIRS:
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

**设计决策**:
- 仅扫描一层深度, 不递归子目录, 避免性能开销
- 忽略以 `.` 开头的隐藏文件
- 仅扫描三个约定子目录名, 不扫描任意目录

### 3.4 Formatter 输出扩展

当前 formatter 输出格式:

```
- my-skill: Description text
  Path: /path/to/SKILL.md
```

扩展后的输出格式:

```
- my-skill: Description text
  Path: /path/to/SKILL.md
  Scripts: scripts/rotate_pdf.py, scripts/validate.py
  References: references/api_docs.md
```

**设计决策**:
- 仅显示文件名(相对于 skill 目录), 不显示绝对路径, 保持 prompt 紧凑
- scripts/references 条目仅在非空时显示
- assets 不在 prompt 中显示(assets 是给输出使用的资源, 不需要 agent 主动读取)
- 在 skill 列表末尾增加一条脚本执行指引

### 3.5 Prompt 引导文本

在 formatter 输出的尾部说明中, 追加 shell 执行指引:

```
When a skill has Scripts listed, you can execute them using the shell tool.
Run scripts directly by their full path shown in the skill's Path prefix.
Only read a skill's SKILL.md when the user's task matches the skill's description.
```

### 3.6 变更范围

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/components/shared/skills/types.py` | 修改 | 增加 `SkillResources` 数据类, `SkillMetadata` 增加 `resources` 字段 |
| `src/components/shared/skills/loader.py` | 修改 | 增加 `_scan_resources` 方法, 在 `load_from_source` 中调用 |
| `src/components/shared/skills/formatter.py` | 修改 | 输出中增加 Scripts/References 行和执行指引 |
| `src/components/shared/skills/__init__.py` | 修改 | 导出 `SkillResources` |

变更量: 约 60 行。

## 4. 改进项 G3: 模板简化

### 4.1 设计方案

修改 `SkillsCommand._skill_template()` 方法, 生成的 SKILL.md 模板对齐 Anthropic 官方最小集。

### 4.2 模板对比

**当前模板**:

```yaml
---
name: {name}
description: >
  TODO: Describe what this skill does and when to use it.
  Include keywords that help the agent recognize relevant tasks.
metadata:
  author: ""
  version: "1.0.0"
  category: general
---
```

**简化后的模板**:

```yaml
---
name: {name}
description: >
  TODO: Describe what this skill does and when to use it.
  Include both what the skill does and specific triggers for when to use it.
---
```

### 4.3 模板 body 调整

同步优化 body 结构, 参照官方的 skill 工程约定:

```markdown
# {name}

TODO: Add skill instructions here.

## Workflow

### Step 1: ...

### Step 2: ...

## Edge Cases

- TODO: Document edge cases and fallback behavior
```

移除 `## When to Use` 小节。原因: 根据 Anthropic 官方 skill-creator 的指导,
"when to use" 信息应全部放在 frontmatter 的 `description` 字段中,
因为 body 部分仅在 skill 被触发后才加载, 此时再声明"何时使用"已无意义。

### 4.4 变更范围

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/application/commands/shared/skills_commands.py` | 修改 | 更新 `_skill_template()` 方法 |

变更量: 约 15 行(替换)。

## 5. 安全性分析

### 5.1 reload 命令

`reload()` 仅重新扫描已配置的 source 目录, 不接受用户传入的路径参数。
source 目录列表在 `resolve_sources()` 中由配置决定, reload 不改变 source 列表。
因此不存在路径注入风险。

### 5.2 脚本路径引导

脚本路径仅作为信息展示在 system prompt 中, skills 系统本身不执行任何脚本。
脚本执行由 `ShellToolMiddleware` 管控, 受其配置的 timeout、output 限制等约束。
skills 系统不绕过也不修改 shell 中间件的安全策略。

文件系统访问方面, skill source 目录已在 factory 中通过 `_extend_filesystem_for_skills()`
添加到 `RealFilesystemMiddleware` 的 `allowed_paths` 中, 且内置 skills 目录已加入
`excluded_paths` 做写保护。新增的 resources 扫描不改变此安全模型。

### 5.3 模板简化

移除字段为纯减法操作, 不影响任何运行时逻辑。`SkillLoader` 的解析逻辑对
`metadata` 字段是可选处理, 移除后不会导致解析失败。

## 6. 兼容性分析

### 6.1 向后兼容

- 已存在的 SKILL.md 文件(包含 `metadata`/`category` 字段)不受影响, loader 解析时跳过未知字段
- `SkillMetadata` 新增 `resources` 字段使用 `field(default_factory=...)`, 不影响现有实例构造
- formatter 输出格式是追加式变更, 不移除现有信息

### 6.2 配置兼容

`skills.json` 配置文件无需修改。reload 命令不依赖新的配置项。

## 7. 测试策略

### 7.1 单元测试

| 测试目标 | 测试要点 |
|----------|----------|
| `_handle_reload` | registry 未初始化时的初始化行为; 已初始化时的重载行为; 异常处理 |
| `_scan_resources` | 有/无子目录; 空目录; 隐藏文件过滤; 多文件排序 |
| `formatter.format` (扩展) | 有 scripts 的 skill 输出; 无 resources 的 skill 输出; 混合场景 |
| `_skill_template` | 生成内容不含 metadata/category; 包含 name 和 description |

### 7.2 集成测试

- 创建临时 skill 目录, 包含 scripts/ 子目录和测试脚本
- 验证 SkillRegistry 加载后 metadata 包含正确的 resources 信息
- 验证 formatter 输出包含 Scripts 行
- 验证 reload 后新增 skill 被正确识别
