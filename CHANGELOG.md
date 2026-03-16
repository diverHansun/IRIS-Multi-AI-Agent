# 更新日志

本文档记录了项目的所有版本更新历史。

## v0.1.4 (2026-03-16)

- **Setup Wizard**: 新增交互式配置向导，支持 `/setup [--llm|--agent|--tools|--dify]` 和 `/doctor` 命令
  - 四步配置流程：LLM Provider → Agent → Tools → Dify，每步可独立运行
  - Esc 全局返回导航，API Key 明文显示，已有值自动回填，跳过不中断流程
  - `/doctor` 全量健康检查，逐项输出 pass / warn / fail
- **prompt_toolkit 输入层** (03-14)：历史记录（↑/↓）、Tab 自动补全、Esc 取消输入
- **LLM 路由重构** (03-15)：以配置驱动的 adapter 路由替代 `LLMProvider` 枚举，新增 tongyi provider 支持
- **配置目录整理** (03-16)：
  - 移除 `config/llm/models/`、`config/agents/basic/models/`、`config/agents/deep/models/` 三个 legacy 子目录
  - 示例文件统一命名为 `providers.example.json`，`.gitignore` 同步更新
  - 默认模型从 `glm-4.5-flash` 升级为 `glm-4.7-flash`

## v0.1.3 (2026-03-13)

- **Deep Agent 终端输出统一** (03-12 ~ 03-13)：重构流式渲染，分离中间过程与最终输出显示通道，消除重复打印
- **语义化 Spinner** (03-13)：各执行阶段使用专属状态图标与计时显示，提升任务进度可读性
- **CLI 渲染器统一** (03-13)：LLM / Basic / Deep 三种引擎共用同一套 transcript UI 框架
- **Deep Agent 配置路径规范化** (03-13)：统一 mainagents / subagents 配置文件路径引用

## v0.1.2 (2026-03-01)

- **Shell 安全策略**: 2026-02-17 至 2026-03-01，新增 `SecurityPolicy` / `ShellExecutor` 抽象，支持运行时动态 HITL 优化；安全策略默认关闭，向后兼容
- **记忆持久化**: `ToolMessage` 每步写入、原子消息组修剪，新增 `SafeMemorySaver` 过滤不可序列化的 `__pregel_tasks/Send` 对象
- **文件系统多路径与编码容错**: `allowed_paths` 扩展支持 `${HOME}` 及任意路径，`case_sensitive` 默认 `false`，`_safe_read` 新增 GB18030 编码回退链
- **Bug 修复**: 修复 `workspace_root` 和 `FileOpTracker` 路径解析错误，将 `project_root` 贯穿整个 HITL 链
- **测试基础设施**: 重写 `run_tests.py` 引入命名套件系统，新增约 25 个单元测试文件

## v0.1.1 (2026-02-17)

- **Skills 系统**: 2026-02-13 至 2026-02-17，新增完整的 Skills 注册/加载/中间件架构，支持项目级与用户级 `.iris/skills/` 目录；新增 reload 命令、资源扫描和模板简化功能
- **流式输出与 MCP 优化**: 修复 Deep Agent 流式渲染异常，重命名 MCP 配置键以统一命名规范
- **测试覆盖**: 新增项目核心模块的全面单元测试套件
- **打包文档**: 更新包命名和安装说明，适配 `uv tool install` 工作流

## v0.1.0 (2026-01-21)

- **首个可发布版本**: 基于 v5.0.0 特性集，完成 `uv tool install` 打包配置（hatchling 构建后端、`iris` CLI 入口点、`config/` 目录打包），支持全局安装与任意目录运行

## v5.0.0 (2026-01-21)

- **配置系统全面重构**: 实现多层级配置管理架构
  - 多层配置解析: 支持环境变量、项目级配置、用户级配置、内置默认配置四层优先级
  - 配置目录结构: 自动创建和管理 ~/.iris/ 用户配置目录（Windows: C:\Users\<用户>\.iris\）
  - 首次运行初始化: 自动复制默认配置文件和模板，提供开箱即用的配置体验
  - 配置加载器: 新增 ConfigLoader 类，统一管理配置文件的查找和加载
  - 配置解析器: 实现 ConfigResolver，支持配置文件的优先级解析和合并
  - 项目上下文集成: 配置系统与项目上下文深度集成，支持项目级配置覆盖
  - 配置文件包含: 更新打包配置，确保 config/ 目录被包含在分发包中
- **项目打包和分发**: 优化全局工具安装体验
  - UV工具支持: 完善 pyproject.toml 配置，支持 uv tool install 全局安装
  - 命令行入口: 配置 iris 命令行入口点，支持在任意目录运行
  - 打包配置优化: 使用 hatchling 构建后端，正确包含 src 和 config 目录
  - 依赖管理: 添加 tomlkit 依赖，用于 TOML 配置文件处理
- **代码全面更新**: 适配新配置系统
  - CLI主程序: 集成配置初始化流程，支持配置热重载
  - 服务层更新: Dify服务使用新配置加载器查找配置文件
  - 工具连接器: 更新 Crawl4AI、MCP 等连接器使用配置加载器
  - SDK适配器: 高德地图、Tavily搜索、智谱搜索等SDK使用新配置系统
  - Provider注册表: LLM、Agent提供商注册表适配新配置路径
  - 工具管理: Ollama工具使用新配置系统
- **文档更新**: 完善配置和安装说明
  - IRIS_SETUP.md: 简化为快速安装指南，提供清晰的打包和配置步骤
  - README.md: 更新快速开始和配置说明章节，反映新的配置架构
  - 配置优先级说明: 详细说明四层配置的优先级和覆盖规则
- **智谱搜索增强** (2026-01-16): 
  - 新增 zhipu_web_crawl 函数，支持Agent引擎直接调用网页爬取功能
  - 扩展智谱搜索SDK功能，提供更丰富的网页内容获取能力
- **容器化支持** (2026-01-16):
  - 添加 Crawl4AI 连接器的 Dockerfile
  - 支持容器化部署爬虫服务
- **记忆系统重构** (2025-12-19):
  - 分离会话管理: LLM、BasicAgent、DeepAgent 会话独立存储和管理
  - 统一记忆架构: 实现统一的 Checkpointer 机制
  - DeepAgent记忆优化: 支持 MemorySaver 和 DeepAgentCheckpointer 两种模式
  - 状态持久化增强: 改进会话状态的保存和恢复机制
  - 会话隔离: 确保不同引擎模式的会话数据互不干扰
- **命令系统优化** (2025-12-19):
  - 更新命令处理逻辑，适配新的记忆架构
  - CLI状态管理改进，支持多引擎会话切换
  - 命令帮助信息优化，提供更清晰的使用指引
- **提示词优化** (2025-12-12):
  - 重构 BasicAgent 提示词模板，提升任务理解能力
  - 优化工具调用提示，改进Agent决策质量
- **日志系统改进** (2025-12-08):
  - 增强工具模块日志输出，提供更详细的调试信息
  - 改进调试模式日志格式，便于问题排查
  - 优化日志级别和输出内容
- **配置和环境改进** (2025-12-05):
  - 优化环境变量加载逻辑
  - 改进配置文件的日志输出
  - 增强配置验证和错误提示
- **向后兼容**: 保持核心API接口稳定，现有功能正常运行

## v4.3.1 (2025-11-28)

- **键盘中断机制完整实现**: 支持所有Agent模式的优雅中断
  - DeepAgent模式: 异常重新抛出确保外层处理器执行,完整的状态持久化和Agent通知
  - BasicAgent模式: 简单中断处理,无状态设计,快速返回
  - LLM模式: 流式响应中断支持,保留部分生成内容,性能指标统计
  - 双Ctrl+C机制: 首次中断操作,二次中断退出(3秒确认窗口)
- **异步异常处理**: 完整的KeyboardInterrupt和asyncio.CancelledError覆盖
  - 5个位置的LLM流式处理器升级
  - 嵌套try-except异常流控制修复
  - 主循环异常传播支持
- **UI主题系统集成**: 添加了统一管理的UI主题色,所有中断消息遵循项目配色和样式规范
  - 移除emoji,使用主题色彩系统
  - 一致的消息格式和Panel样式
- **单元测试验证**: 中断机制测试通过,覆盖KeyboardInterrupt处理流程

## v4.3.0 (2025-11-20)

- **Deep Agent超时处理优化**: 完善超时异常处理和会话持久化机制
  - 消息机制升级: 从内容匹配迁移到类型检测,使用SystemMessage/ToolMessage实现系统通知
  - 统一持久化架构: 提取共享persistence helper,消除MainAgent和SubAgent代码重复
  - ExecutionTimeoutMiddleware重构: 从jump_to模式改为异常抛出,保持checkpoint干净
  - SubAgent超时恢复: 实现SubAgent超时时自动持久化MainAgent状态,防止数据丢失
  - 上下文注入机制: 通过runtime.state传递持久化上下文,避免架构复杂化
- **异常处理统一**:
  - step_timeout和max_execution_time采用统一异常处理流程
  - 超时后自动持久化会话状态,用户可继续对话
  - SystemMessage通知机制,Agent感知超时情况
  - SubAgent超时不中断MainAgent,优雅降级处理
- **架构改进**:
  - 新增shared persistence模块,实现代码复用(DRY原则)
  - MessageFilter从正则匹配升级为类型检测(KISS原则)
  - 状态排除机制,防止内部上下文泄露到SubAgent
  - 更好的容错能力和错误提示
- **测试覆盖**: 21个单元测试全部通过,覆盖所有超时场景

## v4.2.0 (2025-11-03) 

- **Deep Agent模式**: 基于LangGraph的多Agent协作架构
  - 分层设计: Manager协调流程、Factory创建实例、Adapter处理配置、Instance封装逻辑
  - SubAgent中间件: 支持主Agent委派任务给专业子Agent处理
  - 全局记忆系统: 跨会话状态持久化,支持长期对话上下文
  - 运行时中间件: JSON参数解析、工具调用补丁、文件系统增强
- **双文件系统架构**: 安全与灵活并重的文件操作方案
  - 虚拟文件系统: 基于内存的安全沙箱环境,支持快速原型开发
  - 真实文件系统: 受保护的物理文件访问,配合HITL审批机制
  - 智能工具注入: 根据配置动态加载虚拟/真实文件系统工具
  - Glob/Grep工具: 强大的文件搜索和内容检索能力
- **流式输出增强**: 实时交互体验优化
  - 双模式流式: 同时处理messages(token级)和updates(节点级)流
  - 工具调用可视化: 实时显示工具名称、参数和执行结果
  - 文件操作统计: 展示行数变化、文件大小、操作类型
  - Diff实时预览: 文件修改前后对比展示
- **Human-in-the-Loop (HITL)**: 安全操作审批机制
  - 危险操作拦截: 文件写入、编辑、bash命令执行前强制审批
  - Diff预览系统: 显示文件变更统一对比,支持大文件截断
  - 增强UI: 彩色图标(✓/⚡/✗/✏)、单面板布局、原因说明
  - 强制确认: 移除默认值,用户必须显式选择,防止误操作
  - 会话级自动批准: 支持对信任工具设置自动批准偏好
- **配置管理优化**: 灵活的参数控制系统
  - 分离配置: mainagents.json管理主Agent,subagents.json管理子Agent
  - 参数分层: max_execution_time、step_timeout等独立配置
  - 中间件配置: 支持动态启用/禁用各类运行时中间件
  - 危险工具标记: 在配置中标记高风险工具,强制人工审批
- **命令系统扩展**: Deep模式专用命令
  - `/mode deep`: 切换到Deep Agent模式
  - `/deep switch`: 切换主Agent模型
  - `/deep subagents status`: 查看子Agent配置信息
  - `/deep fs`: 文件系统管理命令(ls/cat/write/edit等)
- **向后兼容**: 保持Basic Agent模式完全独立,互不影响

## v4.1.0 (2025-10-19) 

- **LangChain 1.0.0 迁移**: 全面升级到LangChain 1.0.0新版API
  - **Agent架构重构**: 从旧版`AgentExecutor`迁移到新版`CompiledStateGraph`
  - **统一Agent创建**: 使用`create_agent()`替代`create_react_agent()`和`create_tool_calling_agent()`
  - **简化Prompt系统**: 从复杂`PromptTemplate`迁移到简单`system_prompt`字符串
  - **新版状态管理**: 集成LangGraph原生`checkpointer`机制，替代`RunnableWithMessageHistory`
- **输入输出格式适配**:
  - 输入格式: `{"input": str}` → `{"messages": [HumanMessage(...)]}`
  - 输出格式: 保持兼容，自动解析新版消息格式为旧版结构
  - 工具调用信息: 从`intermediate_steps`迁移到`AIMessage.tool_calls`
- **记忆系统增强**: 
  - 新增`BaseAgentCheckpointer`封装类，统一checkpointer配置
  - 支持原生LangGraph状态持久化和会话管理
  - 保持向后兼容，确保现有记忆功能正常
- **代码质量提升**:
  - 更新所有Agent Adapter实现LangChain 1.0.0接口
  - 完善错误处理和日志记录
  - 添加详细的迁移文档和架构设计说明
- **向后兼容**: 保持所有外部API不变，内部实现完全重构

## v4.0.0 (2025-10-13) 

- **架构全面重构**: 实现分层解耦的现代化架构
  - **统一配置层**: ProviderRegistry作为唯一配置入口，消除重复读取
  - **依赖注入**: Adapter通过构造函数接收配置，避免全局状态依赖
  - **职责明确**: Manager协调流程，Adapter处理参数，Instance封装SDK
  - **Provider层移除**: 消除冗余层级，简化调用链路
- **性能优化**:
  - 配置读取优化：从2次降为1次
  - 参数处理优化：从2-3次降为1次
  - 架构层级简化：从6层降为4层
- **参数管理增强**:
  - 三层优先级：user_params > mode_overrides > mode_defaults
  - mode_overrides配置正确生效
  - 特殊逻辑支持（temperature_fixed等）
- **LLM与Agent统一**:
  - 统一的Adapter接口设计
  - 相同的配置驱动方式
  - 一致的参数传递流程
- **文档完善**: 新增架构重构文档，详细记录设计思路和实施过程

## v3.0.0 (2025-10-11) 

- **架构全面升级**: 基于GoF设计模式的企业级架构重构
  - Provider模块化：新增 `src/llm/langchain/providers/` 目录，清晰分离通用与专属工具
  - Ollama迁移：`ollama_http_client.py` → `providers/ollama/client.py`，`OllamaHttpClient` → `OllamaClient`
  - 预留扩展：`providers/zhipu/` 和 `providers/openai/` 为未来专属工具预留空间
- **导入路径优化**: 统一使用绝对导入 (`from src.xxx`)
  - 更新4处关键引用路径（adapter、factory、registry、streaming）
  - 通过6轮导入测试确保架构正确性
- **代码规范化**:
  - 移除部分代码emoji
- **设计模式应用**:
  - Factory: Agent工厂系统 + Registry注册表
  - Adapter: LLM适配器统一provider接口
  - Strategy: 工具管理策略化（SDK/MCP/Connector）
  - Template Method: BaseAgent消除重复代码
- 向后兼容：所有外部API保持不变

## v2.11.0 (2025-10-04)

- **Crawl4AI配置系统完善**: 完整的网页爬取工具配置方案
  - 修复参数传递断层：解决config.json配置无法传递到Docker API的问题
  - 清晰的配置结构：browser/crawler分离，避免参数冗余和混淆
  - 完整的文档体系：
    - `tutorials/connector/crawl4ai/crawl4ai_guide.md` - 详细使用指南和开发目标
    - `config/connector/crawl4ai/README.md` - 配置参考手册和参数速查表
    - `config/connector/crawl4ai/config.template.json` - 简洁配置模板
    - `config/connector/crawl4ai/config.json.commented` - 完整注释配置
  - 参数分层管理：Agent参数 → config.json → 环境变量 → 默认值
  - 代码优化：
    - `src/tools/connector/crawl4ai/config.py` - 简化冗余属性，使用字典结构
    - `src/tools/connector/crawl4ai/adapter.py` - 修复配置字典复制和合并逻辑
  - 完整测试验证：参数传递已验证可用，Agent可正常调用crawl4ai工具
- **LLM配置文件优化**: 改进示例配置文件
  - 完善 `config/llms/example_provider.json` - 涵盖所有schema字段的完整示例
  - 新增3个provider示例（ANTHROPIC、CUSTOM_CLOUD、LOCAL_OLLAMA）
  - 7个model配置示例，覆盖temperature_fixed、parameters、mode_overrides等高级特性
  - 详细的字段说明和使用示例

## v2.10.0 (2025-09-26)

- **工具函数架构重构**: 完善工具函数的组织架构
  - 创建SDK统一工具函数管理器(SDKToolManager)，提供统一的工具获取接口
  - 实现工具函数标准化命名规范：get_available_*_tools()系列函数
  - 重构数学工具：使用get_available_math_tools()统一获取数学工具
  - 重构搜索工具：使用get_available_search_tools()统一获取搜索工具
  - 重构Notion工具：使用get_available_notion_tools()统一获取Notion工具
  - 重构OKX工具：使用get_available_okx_tools()统一获取OKX工具
  - 优化MCP工具：移除src/MCP目录，统一到src/tools/mcp，保持功能独立性
  - 提升代码一致性：所有工具函数遵循相同命名规范
  - 改进Agent集成：统一通过SDKToolManager获取工具列表
  - 确保向后兼容：保持现有功能和API不变

## v2.9.0 (2025-09-20)

- **Dify云端AI集成**: 完整集成Dify云端AI平台
  - 支持文件上传和文档分析，包括PDF、Word、Excel、图片等多种格式
  - 实现多模态理解，支持文本和图像混合对话
  - 流式对话输出，实时显示AI响应
  - 文件一次性使用机制，避免重复发送文件
- **流式输出优化**: 借鉴streaming_llm设计优化Dify流式处理
  - 增加速率控制和性能监控，防止处理过载
  - 智能缓冲机制，提升显示效果和稳定性
  - 可配置的流式参数，支持自定义缓冲大小和延迟
  - 详细的性能统计显示，包括处理速度和数据量
- **文件管理增强**: 新增文件管理命令和功能
  - `files` 命令：查看当前待发送文件列表
  - `clearfiles` 命令：清空待发送文件
  - 自动文件清理机制，对话后自动清空文件列表
  - 改进的帮助信息和用户提示
- **用户体验优化**: 
  - Dify模式专用命令界面，隐藏不相关功能
  - 清晰的配置说明和API密钥设置指南
  - 详细的错误处理和状态显示

## v2.8.0 (2025-09-18)

- **JSON配置系统**: 全面从硬编码配置迁移到灵活的JSON配置
  - 新增 `config/llms/providers.json` 主配置文件
  - 实现 `LLMConfigLoader` 配置加载器，支持缓存和热重载
  - 添加完整的配置验证系统：JSON Schema验证 + 业务逻辑检查
  - 支持自动配置修复和错误处理
  - 新增 `reload` CLI命令，支持配置热重载
- **配置架构优化**:
  - 重构 `src/components/validation.py` 配置验证组件
  - 创建 `config/llms/schema.json` JSON Schema定义
  - 添加 `config/llms/example_provider.json` 示例配置
  - 完善的文档和使用指南
- **MCP配置整理**:
  - 重组MCP配置文件到 `config/mcp/` 目录
  - 更新所有相关路径引用和文档
  - 优化配置文件组织结构
- **向后兼容性**:
  - 保持硬编码备用配置，确保系统稳定性
  - 优雅的降级机制，配置加载失败时自动回退
  - 无破坏性变更，现有用户无需修改使用方式

## v2.7.0 (2025-09-08)

- **Function Calling支持**: 完整集成智谱AI原生Function Calling API
  - 支持GLM-4.5模型的原生工具调用
  - 实现`ZhipuFunctionCallingAgent`和工具适配器
  - 集成完整的MCP工具支持
  - 支持结构化的错误处理和重试机制
- **双模式Agent架构**:
  - Function Calling模式（GLM-4.5）：基于原生API的高效工具调用
  - ReAct模式（其他模型）：基于经典ReAct框架的复杂任务处理
  - 统一的Agent工厂和接口
- **工具适配器优化**:
  - 重命名`tool_adapter.py`为`functioncalling_adapter.py`
  - 增强MCP工具参数处理
  - 完善错误处理和重试机制

## v2.6.0 (2025-09-06)

- **MCP工具支持**: 完整集成Model Context Protocol扩展工具
  - 支持Filesystem MCP：本地文件系统访问
  - 支持Fetch MCP：网页内容获取
  - 支持Notion MCP：Notion页面和数据库交互
  - 完善的MCP配置管理和服务自动启动
- **JSON ReAct补丁**: 解决MCP工具JSON格式输入问题
  - 实现自定义的`JSONReActSingleInputOutputParser`解析器
  - 自动解析JSON格式的工具输入参数
  - 支持字典和数组格式的工具调用
  - 模块化设计，便于在其他项目中复用

## v2.5.0 (2025-08-28)

- **Ollama本地LLM支持**: 新增完整的Ollama本地模型集成
  - 支持gpt-oss:20b、qwen3:8b、gemma3:latest、deepseek-r1:1.5b等主流开源模型
  - 智能模型自动切换：系统启动时自动检测可用模型并切换
  - 工具调用支持：所有支持的模型都具备工具调用能力
  - 健康检查机制：自动检测Ollama服务状态和模型可用性
- **网络代理处理优化**: 彻底重构代理处理机制
  - 移除粗暴的全局代理删除逻辑，避免影响其他服务
  - 支持规则代理配置（如Clash规则模式），智能路由本地和外部服务
  - 保持外部API服务的代理访问能力（OKX、Tavily、Notion等）
  - 提升网络兼容性，适配多种网络环境
- **Agent工厂增强**: 
  - 新增create_ollama_agent函数，支持本地模型Agent创建
  - 统一的Agent创建接口，支持zhipu、openai、ollama三种提供商
  - 自动配置推荐参数，提升本地模型性能
- **配置管理优化**:
  - 新增OLLAMA_BASE_URL、OLLAMA_MODEL等配置选项
  - 支持本地模型的自定义超时、保活等参数配置
  - 向后兼容现有配置，无需修改已有部署

## v2.4.0 (2025-08-15)

- **Notion集成**: 完整的Notion知识管理功能
  - 智能搜索算法：解决相关性排序问题，精确匹配目标内容
  - 页面管理：支持页面信息获取、内容提取、搜索功能
  - 数据库操作：支持数据库查询、记录获取、架构分析
  - Direct API集成：使用原生Notion API，性能稳定可靠
- **智能搜索增强**：
  - 多维度评分算法：精确匹配、子串匹配、字符串相似度、日期格式匹配
  - 备选查询生成：自动生成多种格式的搜索查询提升覆盖率
  - 结果去重排序：基于相关性重新排列搜索结果
- **OpenAI Agent优化**：
  - 解决页面内容获取问题：修复无法获取完整页面内容的bug
  - 工具调用改进：使用隐式工具调用，提升用户体验
  - 多步骤任务支持：自动完成复杂的工具调用序列
- **代码清理和优化**：
  - 移除临时测试文件，保持项目结构清洁
  - 完善错误处理和异常管理
  - 统一同步异步接口，提升代码一致性

## v2.3.0 (2025-08-08)

- **全局记忆系统**: 重构为统一的全局记忆管理架构
  - 跨模式记忆共享(LLM ↔ Agent)
  - 自动消息过滤和上下文管理
  - 智能会话恢复和持久化存储
  - 统一存储到 `data/sessions` 目录
- **架构清理**: 消除代码冗余，优化模块结构
  - 移除重复的记忆管理实现
  - 统一记忆接口和API
  - 完善错误处理和日志记录
- **会话管理增强**: 
  - 自动会话索引和元数据管理
  - 支持会话统计和清理功能
  - 改进的消息修剪和Token管理

## v2.2.0 (2025-08-06)

- **多LLM支持**: 新增OpenAI GPT-4o系列支持
- **Agent工厂**: 统一Agent创建和管理
- **LLM管理器**: 支持动态LLM切换
- **OKX集成**: 新增加密货币分析工具
- **代码优化**: 重构架构，提升可扩展性

## v2.1.0 (2025-07-30)

- **高德地图集成**: 完整的地图服务集成
  - 地点搜索：支持关键词、附近、城市内搜索
  - 驾车导航：智能路线规划和导航指导
  - 步行导航：精确的步行路线规划
  - 公共交通：完整的公交、地铁、综合交通规划
- **公共交通增强**:
  - 详细线路信息显示(线路名称、起终点站、距离时间)
  - 多种路线策略(最快、最经济、最少换乘等)
  - 智能地址解析和坐标转换
  - 城市上下文支持，避免同名地点混淆
- **工具系统优化**:
  - ReAct模式兼容的单参数工具设计
  - 完善的错误处理和参数验证
  - 详细的步行指导和路线展示
- **代码清理**: 移除冗余测试文件，完善文档

## v2.0.0 (2025-07-17)

- **重大更新**: 集成LangChain 2025最佳实践的记忆系统
- **RunnableWithMessageHistory**: 使用标准化的记忆管理模式
- **多用户支持**: 实现会话隔离和持久化存储
- **智能消息修剪**: 基于token和消息数量的自动修剪
- **文档完善**: 新增记忆系统集成文档
- **代码清理**: 移除冗余的memory_manager模块
- **代理修复**: 解决网络代理导致的连接问题

## v1.0.0 (2025-07-16)

- 集成Tavily搜索API
- 优化ReAct提示词模板
- 增强网页内容获取功能
- 修复DuckDuckGo搜索URL解析问题
- 完善错误处理和日志记录

