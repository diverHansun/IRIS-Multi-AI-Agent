# 需求分析与目标定义

## 1. 背景

当前 skills 系统已完成 Phase 1-3 的核心实现, 包括类型定义、加载器、单例注册表、
system prompt 格式化器、SkillsMiddleware 中间件集成以及 `/skills list|create|info` CLI 命令。
但在实际使用中发现三个待改进点。

## 2. 问题分析

### 2.1 缺少 reload 命令

**现状**: `SkillRegistry` 已实现 `reload()` 方法, 能够清空缓存并重新扫描所有已配置的 source 目录。
但该方法仅在代码层可调用, CLI 层未暴露任何入口。

**影响**:
- 用户在会话运行中手动将 skill 文件放入 `~/.iris/skills/` 后, 系统无法识别新增的 skill
- 必须重启整个 agent 会话才能载入新 skill, 开发体验差
- 不利于 skill 开发调试的快速迭代

**需求**: 在 `SkillsCommand` 中增加 `reload` 子命令, 调用 `SkillRegistry.reload()`,
并返回重新加载后的统计信息。

### 2.2 缺少脚本路径引导

**现状**: `SkillPromptFormatter.format()` 仅输出 skill 的 `name`、`description` 和 `path`(SKILL.md 路径)。
agent 不知道 skill 目录中还有可执行的 `scripts/` 子目录。

**对比 Anthropic 官方架构**:
- 官方 skill 架构中, Claude 通过 bash 读取 SKILL.md、执行 `scripts/` 下的脚本
- 脚本代码不进入 context window, 仅脚本输出进入, 显著节省 token
- 官方 skill-creator 的标准目录结构明确包含 `scripts/`、`references/`、`assets/` 三个子目录

**当前系统已有 ShellToolMiddleware**: 提供 `shell` 工具, 支持在持久 shell session 中执行命令。
这意味着 agent 已具备脚本执行能力, 但缺少的是"知道 skill 有哪些脚本可以执行"的信息引导。

**需求**: 在 formatter 输出中扫描 skill 目录下的子资源(scripts、references), 
生成路径信息, 引导 agent 在需要时通过 shell 工具执行脚本或读取参考文档。

### 2.3 模板字段冗余

**现状**: `/skills create` 生成的 SKILL.md 模板包含 `metadata` 字段(含 `author`、`version`、`category`),
这些字段:
- 不属于 Anthropic Agent Skills 官方规范
- 在运行时不参与任何逻辑判断
- `category` 字段无实际用途, 增加了 skill 作者的认知负担

**Anthropic 官方规范 frontmatter 字段**:
- 必需: `name`, `description`
- 可选: `license`, `compatibility`
- 不推荐其他字段: 官方 skill-creator 明确声明 "Do not include any other fields in YAML frontmatter"

**需求**: 简化模板 frontmatter, 移除 `metadata` 块及 `category` 字段, 保留必需字段和合理的可选字段。

## 3. 目标定义

| 编号 | 目标 | 验收标准 |
|------|------|----------|
| G1 | `/skills reload` 命令可用 | 执行后返回重新加载的 skill 数量和错误数量; 新增 skill 文件后执行 reload 能立即被识别 |
| G2 | formatter 输出包含脚本路径引导 | system prompt 中的 skill 条目包含 scripts 和 references 子目录下的文件列表(如果存在) |
| G3 | 模板对齐官方最小集 | `/skills create` 生成的 SKILL.md 仅包含 `name` 和 `description` 必需字段 |

## 4. 非目标

本轮迭代明确不包含以下内容:

- `/skills install` 命令(从 .skill 文件安装)
- `/skills validate` 命令
- `allowed-tools` 运行时强制约束
- 自动检测 skill 目录变更(文件监听)
- skill 版本管理
- basic mode 的 skill 支持
