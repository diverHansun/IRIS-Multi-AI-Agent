# Skills Improve-1: reload 命令与脚本执行引导

> 迭代改进规划文档 - 第一轮

## 文档索引

| 文档 | 说明 | 状态 |
|------|------|------|
| [01-requirements.md](01-requirements.md) | 需求分析与目标定义 | 完成 |
| [02-technical-design.md](02-technical-design.md) | 技术方案设计 | 完成 |
| [03-implementation-plan.md](03-implementation-plan.md) | 实施计划与变更清单 | 完成 |

## 改进范围

本轮迭代聚焦三个改进项:

1. 补全 `/skills reload` CLI 命令
2. 在 formatter 输出中增加脚本路径引导, 使 agent 能够通过 shell 工具执行 skill 绑定的脚本
3. 简化 skill 模板, 移除非官方字段, 对齐 Anthropic Agent Skills 规范

## 设计原则

- 最小侵入: 复用现有 `SkillRegistry.reload()` 和 `ShellToolMiddleware` 基础设施
- 职责清晰: skills 系统负责发现和元数据, shell 中间件负责执行, 两者通过 system prompt 松耦合
- 向后兼容: 不改变现有 SKILL.md 解析逻辑, 仅扩展 formatter 输出格式
