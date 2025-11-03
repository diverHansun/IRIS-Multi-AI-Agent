# Multi-AI-Agent 🤖
基于LangChain和多LLM的中文优化智能代理演示项目，集成了上下文记忆系统、多搜索引擎、高德地图、OKX加密货币和Notion知识管理功能。

## ✨ 一、功能特性

### 核心架构
- **多引擎架构**:
  - **LLM引擎**: 纯对话模式，快速响应，支持流式输出
  - **Agent引擎**: 智能体模式，支持工具调用和复杂推理，包含Basic和Deep两种模式
  - **AgentFlow引擎**: 多智能体工作流编排（开发中）
  - **Dify引擎**: 云端AI平台，支持文件上传、多模态理解、流式对话
- **多LLM提供商**: 智谱AI、OpenAI、Ollama本地模型，支持动态热切换
- **灵活配置系统**: JSON配置文件 + 环境变量，支持热重载（`/reload`命令）

### 智能Agent能力
- **Agent引擎双模式**:
  - **Basic模式**: 基础智能体，适合常规工具调用任务
  - **Deep模式**: 高级智能体，支持任务规划、子代理协作、文件系统操作
- **DeepAgents功能类型**: 研究型（research）、编程型（coding）、分析型（analysis）
- **全局记忆系统**: 统一记忆管理，支持会话隔离和持久化
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

## 🎯 二、工作模式说明

本项目支持四种运行引擎，可通过 `/switch <engine>` 命令动态切换：

### LLM引擎

- **特点**: 快速响应，支持流式输出，纯对话无工具调用
- **适用场景**: 快速问答、创意写作、代码生成等纯对话任务
- **切换命令**: `/switch llm`
- **流式输出**: `/stream on` 开启，`/stream off` 关闭
- **示例**:
  ```
  你 > 写一首关于春天的诗
  AI > [流式输出] 春风拂面...
  ```

### Agent引擎

Agent引擎提供两种模式，可通过 `/mode <basic|deep>` 在引擎内切换：

#### 1. Basic模式（默认）
- **特点**: 基础智能体，支持工具调用和复杂推理
- **适用场景**: 需要搜索、计算、地图导航等工具的常规任务
- **切换命令**: `/switch agent` 然后 `/mode basic`
- **示例**:
  ```
  你 > 搜索北京最新的天气预报
  AI Agent > [调用搜索工具] 为您查询到...
  ```

#### 2. Deep模式
- **特点**: 高级智能体，支持任务规划、子代理协作、文件系统操作
- **功能类型**: 研究型（research）、编程型（coding）、分析型（analysis）
- **适用场景**: 复杂多步骤任务、需要规划的场景、文件操作任务
- **切换命令**: `/switch agent` 然后 `/mode deep`
- **功能切换**: `/use <research|coding|analysis>` 切换DeepAgent功能类型
- **示例**:
  ```
  你 > /mode deep
  你 > /use research
  你 > 研究一下人工智能的最新进展
  AI > [规划任务] → [调用子代理] → [整理结果]...
  ```

### AgentFlow引擎（开发中）

- **特点**: 基于图结构的工作流引擎，支持复杂的多智能体协作和任务编排
- **适用场景**: 复杂工作流、多Agent协作、状态管理
- **切换命令**: `/switch agentflow`

### Dify引擎（云端）

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

### 引擎切换示例
```bash
# 切换到LLM引擎
/switch llm

# 切换到Agent引擎（Basic模式）
/switch agent
/mode basic

# 切换到Agent引擎（Deep模式）
/switch agent
/mode deep
/use research  # 切换到研究型功能

# 在引擎中切换模型（智谱AI）
/model zhipu glm-4.5-flash

# 在引擎中切换模型（OpenAI）
/model openai gpt-4o-mini

# 在引擎中切换模型（Ollama本地）
/model ollama qwen3:8b

# 切换到Dify云端引擎
/switch dify

# 切换到AgentFlow引擎（开发中）
/switch agentflow
```

## 🚀 三、快速开始

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

## 💬 四、常用命令速查

### 全局命令（所有引擎可用）
| 命令 | 说明 | 示例 |
|------|------|------|
| `/help` | 查看帮助信息 | `/help` |
| `/info` | 查看系统状态和配置信息 | `/info` |
| `/exit` 或 `/quit` | 退出程序 | `/exit` |

### 引擎切换
| 命令 | 说明 | 示例 |
|------|------|------|
| `/switch <engine>` | 切换运行引擎 | `/switch llm` |
|  | 可选引擎：llm, agent, agentflow, dify | `/switch agent` |

### LLM引擎专属命令

#### 模型管理
| 命令 | 说明 | 示例 |
|------|------|------|
| `/model <provider> [model]` | 切换LLM提供商和模型 | `/model zhipu glm-4.5-flash` |
| `/llms` | 查看所有可用的LLM模型列表 | `/llms` |
| `/reload` | 热重载LLM配置文件 | `/reload` |

#### 流式输出
| 命令 | 说明 | 示例 |
|------|------|------|
| `/stream <on\|off>` | 开启/关闭流式输出 | `/stream on` |

### Agent引擎专属命令

#### 模型管理
| 命令 | 说明 | 示例 |
|------|------|------|
| `/model <provider> [model]` | 切换LLM提供商和模型 | `/model zhipu glm-4-plus` |
| `/llms` | 查看所有可用的LLM模型列表 | `/llms` |
| `/reload` | 热重载LLM配置文件 | `/reload` |

#### 模式管理
| 命令 | 说明 | 示例 |
|------|------|------|
| `/mode <basic\|deep>` | 切换Agent模式 | `/mode deep` |
| `/use <type>` | 切换DeepAgent功能类型（仅Deep模式） | `/use research` |
| `/deep status` | 查看DeepAgent状态 | `/deep status` |
| `/deep filesystem <mode>` | 设置文件系统权限模式（仅Deep模式） | `/deep filesystem read-only` |

#### 工具管理
| 命令 | 说明 | 示例 |
|------|------|------|
| `/mcp status [-v]` | 查看MCP工具状态 | `/mcp status -v` |
| `/mcp tools [--json]` | 列出MCP工具列表 | `/mcp tools` |
| `/mcp reload` | 重载MCP配置 | `/mcp reload` |
| `/connector status [-v]` | 查看Connector工具状态 | `/connector status` |
| `/connector tools [--json]` | 列出Connector工具列表 | `/connector tools` |
| `/connector reload` | 重载Connector配置 | `/connector reload` |

#### 会话管理
| 命令 | 说明 | 示例 |
|------|------|------|
| `/new` | 创建新会话 | `/new` |
| `/clear` | 清空当前会话记忆 | `/clear` |
| `/sessions` | 查看历史会话列表 | `/sessions` |
| `/restore <session_id>` | 恢复指定会话 | `/restore session_20250101_120000` |
| `/delete_session <session_id>` | 删除指定会话 | `/delete_session session_20250101_120000` |
| `/cleanup` | 清理孤立的会话文件 | `/cleanup` |

### AgentFlow引擎专属命令（开发中）

| 命令 | 说明 | 示例 |
|------|------|------|
| `/graph <name>` | 选择或切换图 | `/graph workflow` |
| `/nodes` | 查看当前图的节点 | `/nodes` |
| `/visualize` | 可视化当前图结构 | `/visualize` |
| `/model <provider> [model]` | 切换LLM提供商和模型 | `/model zhipu glm-4-plus` |

### Dify引擎专属命令

#### 文件管理
| 命令 | 说明 | 示例 |
|------|------|------|
| `/upload [文件路径]` | 上传文件（支持多选对话框） | `/upload report.pdf` |
| `/files` | 查看待发送文件列表 | `/files` |
| `/files remove <序号>` | 移除指定文件 | `/files remove 2` |
| `/files clear` | 清空所有待发送文件 | `/files clear` |

#### 会话管理
| 命令 | 说明 | 示例 |
|------|------|------|
| `/reset` | 重置Dify会话（清除记忆和文件） | `/reset` |
| `/reconnect` | 重新连接Dify服务 | `/reconnect` |

### 使用提示
- 所有命令都以 `/` 开头
- 命令不区分大小写
- 不同引擎下可用命令不同：
  - **全局命令**: 所有引擎都可用
  - **LLM专属**: 仅在 `/switch llm` 后可用
  - **Agent专属**: 仅在 `/switch agent` 后可用
  - **AgentFlow专属**: 仅在 `/switch agentflow` 后可用（开发中）
  - **Dify专属**: 仅在 `/switch dify` 后可用
- 使用 `/help` 查看当前引擎下可用的所有命令

## 📊 五、支持的LLM模型

本项目支持多个LLM提供商，在LLM引擎和Agent引擎下可通过 `/model <provider> [model]` 命令动态切换。

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
# 切换到LLM引擎或Agent引擎
/switch llm
# 或
/switch agent

# 智谱AI - 免费闪电版（推荐入门）
/model zhipu glm-4.5-flash

# 智谱AI - Function Calling模式
/model zhipu glm-4.5

# OpenAI - GPT-5
/model openai gpt-5

# Ollama - 本地模型(仅LLM引擎，需自行配置)
/model ollama qwen3:8b
```

### Ollama本地模型使用

Ollama支持完全离线运行，需要自行下载模型：

```bash
# 1. 安装Ollama（访问 https://ollama.com/）
# 2. 下载模型
ollama pull qwen3:8b
ollama pull gpt-oss:20b

# 3. 在项目中使用
/switch llm  # 或 /switch agent
/model ollama qwen3:8b
```

> **💡 提示**:
> - 详细配置参见 `config/llm/models/providers.json`
> - 使用 `/llms` 命令查看所有可用模型
> - OpenAI的GPT-5系列温度固定为1.0，无法调整


## ⚙️ 六、配置说明

### 配置优先级

项目支持多层级配置，优先级从高到低：

1. **环境变量** (`.env` 文件) - API密钥、默认模型等
2. **JSON配置文件** (`config/llm/models/providers.json`) - 模型参数、特性等
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

使用 `config/llm/models/providers.json` 自定义模型参数：

- **模型参数覆盖**: `mode_overrides` 字段可针对不同模式设置不同参数
- **温度固定**: 部分模型（如GPT-5）的温度参数固定，无法通过配置修改
- **工具支持**: `supports_tools` 字段控制模型是否启用工具调用

DeepAgent配置：
- 主代理配置：`config/agents/deep/models/mainagents.json`
- 子代理配置：`config/agents/deep/models/subagents.json`
- 中间件配置：`config/agents/deep/middleware/`

详细配置说明请参考：
- 配置文件：`config/llm/models/providers.json`
- 配置模板：`.env.example`
- 示例配置：相关目录下的`example`文件

> **💡 配置热重载**: 修改配置文件后，使用 `/reload` 命令即可生效，无需重启程序

## 📝 七、更新日志

完整更新历史请查看 [CHANGELOG.md](CHANGELOG.md)
