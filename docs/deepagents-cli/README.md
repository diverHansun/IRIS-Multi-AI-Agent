# DeepAgents CLI 优化实施文档

本目录包含了从 `deepagents-cli` 官方实现中借鉴的设计和优化方案，分为5个阶段实施。

## 重要提示

**在开始实施5个优化阶段之前，请先阅读并执行目录结构优化**：
[00-directory-restructure.md](./00-directory-restructure.md)

目录结构优化将为后续实施提供清晰的代码组织基础，避免在实施过程中频繁修改导入路径。

## 文档索引

### 前置准备：目录结构优化
[00-directory-restructure.md](./00-directory-restructure.md)

优化目录结构，为后续实施提供清晰的代码组织基础。

### 阶段1：Agent记忆系统
[01-agent-memory-system.md](./01-agent-memory-system.md)

实现agent的长期记忆加载和更新机制，让agent能够记住用户偏好和学习模式。

### 阶段2：文件操作追踪和Diff预览
[02-file-operation-tracking.md](./02-file-operation-tracking.md)

增强文件操作的可视化，在HITL审批前显示diff预览，操作后显示详细结果。

### 阶段3：HITL交互体验增强
[03-hitl-interaction-enhancement.md](./03-hitl-interaction-enhancement.md)

改善人机交互体验，提供工具特定的格式化显示和更清晰的审批选项。

### 阶段4：流式处理双模式支持
[04-streaming-dual-mode.md](./04-streaming-dual-mode.md)

优化流式处理机制，分离内容流和元数据流，提升响应速度和显示质量。

### 阶段5：用户输入增强
[05-input-enhancement.md](./05-input-enhancement.md)

实现 `@文件` 引用语法，自动将文件内容注入到查询上下文中。

## 实施顺序建议

建议按照阶段顺序实施，因为：

1. **阶段1** 建立记忆管理基础，是其他功能的基础
2. **阶段2** 提升安全性和透明度，对用户体验影响大
3. **阶段3** 改善交互体验，依赖阶段2的预览功能
4. **阶段4** 优化性能，独立性强，可并行实施
5. **阶段5** 提供便利功能，实施相对独立

## 文档结构

每篇文档都遵循以下结构：

1. **deepagents-cli官方代码的优点**：分析官方实现的设计亮点
2. **我们现有代码的优点和不足**：评估当前实现，明确改进方向
3. **实施方案**：详细的实施步骤、文件路径和注意事项

## 注意事项

- 所有实施都要保持向后兼容
- 新功能通过配置开关控制启用/禁用
- 优先保证现有功能的稳定性
- 充分测试后再合并到主分支

