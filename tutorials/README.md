# Multi-AI-Agent 教程集合

本目录包含项目相关的技术教程和学习资源，涵盖AI代理开发、工具集成、测试实践等多个方面。

## 教程分类

### 🤖 Agent 构建 (agent_building)
- **[LangChain框架教程](agent_building/langchain_tutorial.md)** - LangChain框架的使用指南和实践教程，包含代理构建、工具集成等核心概念
- **[函数调用开发指南](agent_building/function_calling_guide.md)** - 智谱AI函数调用(Function Calling)开发与使用指南，专为 `glm-4.5` 模型设计

### 🔗 连接器 (connector)
- **[Crawl4AI连接器指南](connector/crawl4ai/crawl4ai_guide.md)** - 基于HTTP的网络爬虫工具，为AI代理提供高质量的网页内容提取功能

### 🌐 集成服务 (dify)
- **[Dify集成开发指南](dify/dify_guide.md)** - Dify云平台集成指南，支持文件上传、多模态理解和流式对话功能

### 🛠️ MCP工具 (mcp)
- **[MCP工具使用指南](mcp/mcp_guide.md)** - Model Context Protocol工具的配置和使用教程，包含Context7、Firecrawl等MCP服务器

### 🔄 流程控制 (process)
- **[主流程控制指南](process/main/main_guide.md)** - 主流程控制与连接器系统开发指南，涵盖CLI设计、多模式支持等

### 🧪 测试实践 (test)
- **[软件测试入门教程](test/software_testing_guide.md)** - 从零开始学习软件测试的概念、方法和最佳实践


## 学习路径建议

### 🚀 新手开发者
**基础入门路径：**
1. 先阅读 **[软件测试入门教程](test/software_testing_guide.md)**，理解测试的重要性
2. 学习 **[LangChain框架教程](agent_building/langchain_tutorial.md)**，掌握AI应用开发基础
3. 了解 **[主流程控制指南](process/main/main_guide.md)**，理解项目架构
4. 实践 **[函数调用开发指南](agent_building/function_calling_guide.md)**，掌握AI代理开发

**进阶学习路径：**
1. 集成 **[Dify集成开发指南](dify/dify_guide.md)**，体验云端AI服务
2. 配置 **[MCP工具使用指南](mcp/mcp_guide.md)**，扩展AI代理能力
3. 使用 **[Crawl4AI连接器指南](connector/crawl4ai/crawl4ai_guide.md)**，实现网页内容抓取

### 🔧 有经验的开发者
**快速上手：**
1. 直接查阅对应技术的教程文档
2. 结合项目的测试框架进行实际应用
3. 根据需求选择合适的集成方案

**深度定制：**
1. 基于现有连接器开发新的集成方案
2. 扩展MCP工具支持更多外部服务
3. 优化主流程控制逻辑
4. 参与贡献更多教程内容

## 如何使用教程

### 📖 阅读建议
- 每个教程都是独立的Markdown文档，可以单独阅读
- 教程中的示例代码都基于本项目的实际代码
- 建议边阅读边实践，加深理解
- 按照学习路径顺序阅读，效果更佳

### 🛠️ 实践指南
- 确保环境配置正确（Node.js 18+, Python 3.8+）
- 按照教程步骤逐步操作
- 遇到问题时参考故障排查部分
- 结合项目实际代码进行调试

## 教程特色

### ✨ 核心亮点
- **实用性强**：所有教程都基于项目实际需求编写
- **代码完整**：提供完整可运行的代码示例
- **循序渐进**：从基础概念到高级应用，层次分明
- **中文友好**：全中文文档，降低学习门槛

### 🎯 适用场景
- AI代理开发学习
- LangChain框架实践
- 多模态AI应用开发
- 企业级AI系统集成

## 贡献教程

### 🤝 欢迎贡献
欢迎贡献新的教程内容！请确保：

**内容要求：**
- 使用清晰的Markdown格式
- 提供实际可运行的代码示例
- 内容通俗易懂，适合不同水平的读者
- 包含完整的配置和使用说明

**提交规范：**
- 在对应分类目录下创建教程文件
- 更新本README文件添加新教程链接
- 遵循现有的文档结构和风格
- 提供完整的测试验证

### 📝 贡献流程
1. Fork 项目仓库
2. 创建新的教程分支
3. 编写教程内容
4. 更新README文件
5. 提交Pull Request