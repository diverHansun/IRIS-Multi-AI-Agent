# Multi-AI-Agent 🤖
基于LangChain和多LLM的中文优化智能代理演示项目，集成了上下文记忆系统、多搜索引擎、高德地图、OKX加密货币和Notion知识管理功能。

## ✨ 功能特性

### 核心架构
- **双模式运行架构**:
  - **本地模式**: Agent模式（工具调用+复杂推理）、LLM模式（快速对话+流式输出）
  - **Dify云端模式**: 云端AI平台，支持文件上传、多模态理解、流式对话
- **多LLM提供商**: 智谱AI、OpenAI、Ollama本地模型，支持动态热切换
- **灵活配置系统**: JSON配置文件 + 环境变量，支持热重载（`/reload`命令）

### 智能Agent能力
- **双Agent框架**:
  - **Function Calling模式**（GLM-4.5）：基于智谱AI原生API的高效工具调用
  - **ReAct推理框架**（GLM-4-Plus等）：基于经典ReAct的多步骤任务处理
- **全局记忆系统**: 基于LangChain 2025最佳实践的统一记忆管理，支持会话隔离和持久化
- **工具生态系统**:
  - **MCP工具**: Model Context Protocol扩展工具（文件系统、网页获取、Notion等）
  - **Connector工具**: 外部服务连接器（Crawl4AI智能爬虫等）
  - **SDK工具**: 数学计算、Tavily搜索、高德地图、OKX加密货币等

### 增强功能
- **Dify文件处理**: 支持文档分析、图片识别，文件一次性使用机制
- **多搜索引擎**: Tavily搜索API + DuckDuckGo备用降级
- **高德地图集成**: 地点搜索、路线规划（驾车/步行/公交）
- **OKX加密货币**: 实时行情、K线分析、市场洞察
- **Notion集成**: 智能搜索、页面管理、数据库操作
- **中文优化**: 针对中文场景优化的提示词和交互体验
- **智能降级**: 自动降级到备用方案保证服务可用性

## 🎯 工作模式说明

本项目支持三种工作模式，可通过命令动态切换：

### 本地模式

#### 1. Agent模式（推荐）
- **特点**: 完整功能，支持工具调用和复杂推理
- **适用场景**: 需要搜索、计算、地图导航等工具的复杂任务
- **切换命令**: `/mode agent`
- **示例**:
  ```
  你 > 搜索北京最新的天气预报
  AI Agent > [调用搜索工具] 为您查询到...
  ```

#### 2. LLM模式
- **特点**: 快速响应，支持流式输出，纯对话无工具调用
- **适用场景**: 快速问答、创意写作、代码生成等纯对话任务
- **切换命令**: `/mode llm`
- **流式输出**: `/stream on` 开启，`/stream off` 关闭
- **示例**:
  ```
  你 > 写一首关于春天的诗
  AI > [流式输出] 春风拂面...
  ```

### Dify云端模式

- **特点**: 集成Dify云端AI平台，支持文件上传和多模态理解
- **适用场景**: 文档分析、图片识别、多模态对话
- **切换命令**: `/switch dify`
- **文件支持**:
  - 文档类：`.pdf`、`.docx`、`.xlsx`、`.txt`、`.md`等
  - 图片类：`.jpg`、`.png`、`.gif`、`.webp`等
  - 最大文件：10MB/文件
- **示例**:
  ```
  你 > /upload document.pdf
  你 > 这个文档主要讲了什么？
  AI > [分析文档] 该文档主要介绍了...
  ```

### 模式切换示例
```bash
# 切换到本地Agent模式（智谱AI）
/switch zhipu glm-4-plus

# 切换到本地LLM模式（OpenAI）
/switch openai gpt-4o-mini

# 切换到Ollama本地模型
/switch ollama qwen3:8b

# 切换到Dify云端模式
/switch dify
```

## 🚀 快速开始

### 1. 环境准备

确保您的Python版本 >= 3.8

```bash
# 克隆项目
git clone <your-repo-url>
cd Multi-AI-Agent

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 激活虚拟环境 (Linux/Mac)
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置API密钥

支持的API服务：

1. **智谱AI** - [智谱AI开放平台](https://open.bigmodel.cn/) (必需)
2. **OpenAI** - [OpenAI API](https://platform.openai.com/) (可选)
3. **Ollama本地模型** - [Ollama](https://ollama.com/) (可选，支持本地离线运行)
4. **Tavily搜索** - [Tavily](https://tavily.com/) (推荐)
5. **高德地图** - [高德地图开放平台](https://lbs.amap.com/dev/key/app) (推荐)
6. **Notion** - [Notion API](https://developers.notion.com/) (可选)

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```env
# 必需 - 至少配置一个LLM
ZHIPU_API_KEY=your_zhipu_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Ollama本地模型配置(可选)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b
# 建议使用规则代理模式以获得最佳网络兼容性

# 推荐 - 搜索和地图功能
TAVILY_API_KEY=your_tavily_api_key_here
AMAP_API_KEY=your_amap_api_key_here

# Dify云端AI平台(可选)
DIFY_API_KEY=your_dify_api_key_here
DIFY_BASE_URL=https://api.dify.ai/v1

# 可选 - Notion知识管理
NOTION_TOKEN=your_notion_integration_token_here

# 可选 - 加密货币功能
# OKX_API_KEY=your_okx_api_key_here
# OKX_SECRET_KEY=your_okx_secret_key_here
# OKX_PASSPHRASE=your_okx_passphrase_here

# LLM配置
DEFAULT_LLM_PROVIDER=zhipu OR openai OR ollama
DEFAULT_LLM_MODEL=glm-4-plus OR gpt-4o
```

### 3. 运行程序

```bash
# 启动交互式CLI
python main.py
```

## 💬 常用命令速查

### 基础命令
| 命令 | 说明 |
|------|------|
| `/help` | 查看帮助信息 |
| `/info` | 查看系统状态和配置信息 |
| `/llms` | 查看所有可用的LLM模型列表 |
| `/exit` 或 `/quit` | 退出程序 |

### 模式和模型切换
| 命令 | 说明 | 示例 |
|------|------|------|
| `/switch <provider> [model]` | 切换LLM提供商和模型 | `/switch zhipu glm-4-plus` |
| `/switch dify` | 切换到Dify云端模式 | `/switch dify` |
| `/mode llm` | 切换到LLM模式（快速对话） | `/mode llm` |
| `/mode agent` | 切换到Agent模式（工具调用） | `/mode agent` |
| `/stream on/off` | 开启/关闭流式输出（仅LLM模式） | `/stream on` |
| `/reload` | 热重载LLM配置文件 | `/reload` |

### 会话管理
| 命令 | 说明 | 示例 |
|------|------|------|
| `/clear` | 清空当前会话记忆 | `/clear` |
| `/new` | 创建新会话 | `/new` |
| `/sessions` | 查看历史会话列表 | `/sessions` |
| `/restore <session_id>` | 恢复指定会话 | `/restore session_20250101_120000` |
| `/delete_session <session_id>` | 删除指定会话 | `/delete_session session_20250101_120000` |
| `/cleanup` | 清理孤立的会话文件 | `/cleanup` |

### 文件管理（Dify模式）
| 命令 | 说明 | 示例 |
|------|------|------|
| `/upload [文件路径]` | 上传文件（支持多选对话框） | `/upload report.pdf` |
| `/files` | 查看待发送文件列表 | `/files` |
| `/files remove <序号>` | 移除指定文件 | `/files remove 2` |
| `/files clear` | 清空所有待发送文件 | `/files clear` |
| `/reset` | 重置Dify会话（清除记忆和文件） | `/reset` |

### 工具管理
| 命令 | 说明 | 示例 |
|------|------|------|
| `/mcp status [-v]` | 查看MCP工具状态 | `/mcp status -v` |
| `/mcp tools [--json]` | 列出MCP工具列表 | `/mcp tools` |
| `/mcp reload` | 重载MCP配置 | `/mcp reload` |
| `/connector status [-v]` | 查看Connector工具状态 | `/connector status` |
| `/connector tools [--json]` | 列出Connector工具列表 | `/connector tools` |
| `/connector reload` | 重载Connector配置 | `/connector reload` |

### 使用提示
- 所有命令都以 `/` 开头
- 命令不区分大小写
- 在Dify模式下，部分命令（如`/mcp`、`/connector`）不可用
- 使用 `/help` 查看当前模式下可用的所有命令

## 📊 支持的LLM模型

本项目支持多个LLM提供商，可通过 `/switch <provider> [model]` 命令动态切换。

### 模型概览

| Provider | 推荐模型 | 核心特性 | 适用场景 |
|----------|----------|----------|----------|
| **智谱AI** | `glm-4.5-flash` ⭐ | 免费、128K上下文、思考模式 | 通用任务、成本敏感场景 |
| | `glm-4.5` | 96K输出、Function Calling | 代码生成、复杂推理 |
| | `glm-4-plus` | ReAct框架、综合能力强 | 多步骤任务、通用对话 |
| **OpenAI** | `gpt-5` ⭐ | 高级推理、温度固定(1.0) | 创意写作、复杂推理 |
| | `gpt-5-mini` | 快速推理、32K输出 | 快速响应、成本优化 |
| | `gpt-4o-mini` | 多模态、16K输出 | 通用任务、长上下文 |
| **Ollama** | `qwen3:8b` ⭐ | 本地部署、中文优化 | 离线场景、隐私优先 |
| | `gpt-oss:20b` | 工具调用、开源GPT | 复杂推理、本地Agent |

### 快速切换示例

```bash
# 智谱AI - 免费闪电版（推荐入门）
/switch zhipu glm-4.5-flash

# 智谱AI - Function Calling模式
/switch zhipu glm-4.5

# OpenAI - GPT-5
/switch openai gpt-5

# Ollama - 本地模型
/switch ollama qwen3:8b
```

### Ollama本地模型使用

Ollama支持完全离线运行，需要自行下载模型：

```bash
# 1. 安装Ollama（访问 https://ollama.com/）
# 2. 下载模型
ollama pull qwen3:8b
ollama pull gpt-oss:20b

# 3. 在项目中使用
/switch ollama qwen3:8b
```

> **💡 提示**:
> - 详细配置参见 `config/llms/providers.json`
> - 使用 `/llms` 命令查看所有可用模型
> - OpenAI的GPT-5系列温度固定为1.0，无法调整


## ⚙️ 配置说明

### 配置优先级

项目支持多层级配置，优先级从高到低：

1. **环境变量** (`.env` 文件) - API密钥、默认模型等
2. **JSON配置文件** (`config/llms/providers.json`) - 模型参数、特性等
3. **代码默认值** - 兜底配置

### 核心配置项

| 配置项 | 说明 | 示例 | 必需 |
|--------|------|------|------|
| `ZHIPU_API_KEY` | 智谱AI API密钥 | `abcd1234.efgh5678...` | ✅ 二选一 |
| `OPENAI_API_KEY` | OpenAI API密钥 | `sk-xxxxxxxx...` | ✅ 二选一 |
| `OLLAMA_BASE_URL` | Ollama服务地址 | `http://localhost:11434` | ❌ |
| `DEFAULT_LLM_PROVIDER` | 默认提供商 | `zhipu` / `openai` / `ollama` | ❌ |
| `DEFAULT_LLM_MODEL` | 默认模型 | `glm-4.5-flash` / `gpt-4o-mini` | ❌ |
| `DIFY_API_KEY` | Dify云端API密钥 | `app-xxxxxxxx...` | ❌ |
| `TAVILY_API_KEY` | Tavily搜索API密钥 | `tvly-xxxxxxxx...` | ❌ 推荐 |
| `AMAP_API_KEY` | 高德地图API密钥 | `xxxxxxxx...` | ❌ 推荐 |
| `NOTION_TOKEN` | Notion集成Token | `ntn_xxxxxxxx...` | ❌ |

### 高级配置

使用 `config/llms/providers.json` 自定义模型参数：

- **模型参数覆盖**: `mode_overrides` 字段可针对LLM/Agent模式设置不同参数
- **温度固定**: 部分模型（如GPT-5）的温度参数固定，无法通过配置修改
- **工具支持**: `supports_tools` 字段控制模型是否启用工具调用

详细配置说明请参考：
- 配置文件：`config/llms/providers.json`
- 配置模板：`.env.example`
- 示例配置：`config/llms/example_provider.json`

> **💡 配置热重载**: 修改 `providers.json` 后，使用 `/reload` 命令即可生效，无需重启程序

## 📝 更新日志

### v3.0.0 (2025-10-11) 🎉
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

### v2.11.0 (2025-10-04)
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

### v2.10.0 (2025-09-26)
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

### v2.9.0 (2025-09-20)
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

### v2.8.0 (2025-09-18)
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

### v2.7.0 (2025-09-08)
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

### v2.6.0 (2025-09-06)
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

### v2.5.0 (2025-08-28)
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

### v2.4.0 (2025-08-15)
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

### v2.3.0 (2025-08-08)
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

### v2.2.0 (2025-08-06)
- **多LLM支持**: 新增OpenAI GPT-4o系列支持
- **Agent工厂**: 统一Agent创建和管理
- **LLM管理器**: 支持动态LLM切换
- **OKX集成**: 新增加密货币分析工具
- **代码优化**: 重构架构，提升可扩展性

### v2.1.0 (2025-07-30)
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

### v2.0.0 (2025-07-17)
- **重大更新**: 集成LangChain 2025最佳实践的记忆系统
- **RunnableWithMessageHistory**: 使用标准化的记忆管理模式
- **多用户支持**: 实现会话隔离和持久化存储
- **智能消息修剪**: 基于token和消息数量的自动修剪
- **文档完善**: 新增记忆系统集成文档
- **代码清理**: 移除冗余的memory_manager模块
- **代理修复**: 解决网络代理导致的连接问题

### v1.0.0 (2025-07-16)
- 集成Tavily搜索API
- 优化ReAct提示词模板
- 增强网页内容获取功能
- 修复DuckDuckGo搜索URL解析问题
- 完善错误处理和日志记录