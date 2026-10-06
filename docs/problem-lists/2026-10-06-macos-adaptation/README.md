# macOS 本机适配

目标：在本机虚拟环境中安装 IRIS，修正从 Windows 迁移时的配置与路径问题。

本议题只有一轮，improve-1 开始于 2026-10-06。用户已要求直接完成适配和安装；规划、实施、验证在当前任务中连续进行。

## 文档地图

- [00：需求来源](improve-1/00-discussion.md)
- [01：现状与问题](improve-1/01-problem-analysis-and-current-state.md)
- [02：实施方案](improve-1/02-optimization-plan-and-change-scope.md)
- 03 跳过：本轮没有外部参考项目。
- [04：测试与验收标准](improve-1/04-test-and-acceptance.md)
- [05：实施验收](improve-1/05-implementation-acceptance.md)

配置目录沿用 ~/.iris；依赖安装到项目 .venv。用户已选择 ZenMux 的 `openai/gpt-6-luna`，并授权复用本机已有密钥；BasicAgent 与 DeepAgent 的真实对话均已验证。MCP 服务和 Crawl4AI 服务仍需各自配置后验证。
