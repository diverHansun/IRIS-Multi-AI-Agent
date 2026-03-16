# IRIS:Multi-AI-Agent 🤖
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

本项目支持四种运行引擎，通过 `/switch` 命令动态切换：

| 引擎 | 说明 | 适用场景 |
|------|------|----------|
| **LLM** | 纯对话模式，支持流式输出 | 快速问答、创意写作、代码生成 |
| **Agent** | 智能体模式，支持 Basic/Deep 两种子模式 | 工具调用、任务规划、子代理协作 |
| **AgentFlow** | 多智能体工作流编排（开发中） | 复杂工作流、多Agent协作 |
| **Dify** | 云端AI平台，支持文件上传和多模态 | 文档分析、图片识别 |

## 🚀 三、快速开始

### 1. 环境准备

确保您的Python版本 >= 3.10，并已安装 [uv](https://github.com/astral-sh/uv) 包管理器。

```bash
# 克隆项目
git clone <your-repo-url>
cd Multi-AI-Agent

# 使用uv创建虚拟环境并安装依赖
uv sync
```

### 2. 打包安装

使用 uv 工具安装后，可在项目根目录直接运行 `iris` 命令。

- 品牌名称: `IRIS:muti-ai-agent`
- Python 分发包名: `iris-muti-ai-agent`（用于 `uv tool` 安装管理）

```powershell
# Windows PowerShell
.venv\Scripts\activate
uv tool uninstall muti-ai-agent 2>$null
uv tool uninstall iris-muti-ai-agent 2>$null
uv tool install --python .venv\Scripts\python.exe --editable --force --reinstall --refresh --no-cache .
```

```bash
# Linux/Mac
source .venv/bin/activate
uv tool uninstall muti-ai-agent || true
uv tool uninstall iris-muti-ai-agent || true
uv tool install --python .venv/bin/python --editable --force --reinstall --refresh --no-cache .
```

### 3. 配置API密钥

首次运行会自动创建 `~/.iris/` 全局配置目录（Windows: `C:\Users\<你>\.iris\`）。

支持的API服务：

1. **智谱AI** - [智谱AI开放平台](https://open.bigmodel.cn/) (必需)
2. **OpenAI** - [OpenAI API](https://platform.openai.com/) (可选)
3. **Ollama本地模型** - [Ollama](https://ollama.com/) (可选，支持本地离线运行)
4. **Tavily搜索** - [Tavily](https://tavily.com/) (推荐)
5. **高德地图** - [高德地图开放平台](https://lbs.amap.com/dev/key/app) (推荐)
6. **Notion** - [Notion API](https://developers.notion.com/) (可选)

配置API密钥：

```powershell
# Windows PowerShell
cd $env:USERPROFILE\.iris
Copy-Item .env.example .env -Force
notepad .env  # 编辑并填写API密钥
```

```bash
# Linux/Mac
cd ~/.iris
cp .env.example .env
nano .env  # 编辑并填写API密钥
```

`.env` 文件配置示例：
```env
# 必需 - 至少配置一个LLM
ZHIPU_API_KEY=your_zhipu_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Ollama本地模型配置(可选)
OLLAMA_BASE_URL=http://localhost:11434

# 推荐 - 搜索和地图功能
TAVILY_API_KEY=your_tavily_api_key_here
AMAP_API_KEY=your_amap_api_key_here

# Dify云端AI平台(可选)
DIFY_API_KEY=your_dify_api_key_here

# 可选 - Notion知识管理
NOTION_TOKEN=your_notion_integration_token_here

# LLM配置
DEFAULT_LLM_PROVIDER=zhipu
DEFAULT_LLM_MODEL=glm-4.7-flash
```

### 4. 运行程序

在项目根目录下运行：

```bash
iris
```

> **💡 提示**: 首次运行会自动初始化配置目录，后续可在任意位置运行 `iris` 命令启动。

### 5. 更新程序

修改代码后，重新打包安装：

```powershell
# Windows PowerShell
uv tool install --python .venv\Scripts\python.exe --editable --force --reinstall --refresh --no-cache .
```

```bash
# Linux/Mac
uv tool install --python .venv/bin/python --editable --force --reinstall --refresh --no-cache .
```

### 6. 启动 Crawl4AI Connector 服务（Docker）

项目根目录已提供 `docker-compose.yml`，可直接启动：

```powershell
# 启动 Crawl4AI 服务
docker compose up -d crawl4ai

# 查看状态
docker compose ps crawl4ai

# 查看最近日志
docker compose logs --tail 100 crawl4ai

# 健康检查
Invoke-WebRequest http://localhost:11235/health
```

```bash
# 启动 Crawl4AI 服务
docker compose up -d crawl4ai

# 查看状态
docker compose ps crawl4ai

# 查看最近日志
docker compose logs --tail 100 crawl4ai

# 健康检查
curl http://localhost:11235/health
```

服务启动后可在 CLI 中验证：

```text
/connector status
/connector tools
```
## 💬 四、命令与交互

启动后输入 `/help` 查看所有可用命令。支持 **Tab 自动补全**：输入 `/` 后按 Tab 即可浏览当前引擎可用的命令及参数。

## 📊 五、支持的LLM模型

在LLM引擎和Agent引擎下可通过 `/model <provider> [model]` 命令动态切换。

| Provider | 模型 | 说明 |
|----------|------|------|
| **智谱AI** | `glm-4.7-flash` ⭐ | 免费、128K上下文、默认推荐 |
| | `glm-4.7` | 高性能思考模型 |
| | `glm-4-plus` | 综合能力强 |
| **OpenAI** | `gpt-4o-mini` ⭐ | 轻量高性价比 |
| | `gpt-4o` | 通用旗舰 |
| | `gpt-5` / `gpt-5-mini` | 最新推理模型，温度固定(1.0) |
| **通义千问** | `qwen3-max` ⭐ | 全能旗舰 |
| | `qwen3-coder-plus` | 代码优化 |
| **Ollama** | `qwen3:8b` | 本地部署、离线运行 |

```bash
/model zhipu glm-4.7-flash   # 智谱AI 免费版（默认）
/model openai gpt-4o-mini    # OpenAI 轻量版
/model tongyi qwen3-max      # 通义千问
/model ollama qwen3:8b       # 本地模型
```

> 使用 `/llms` 查看所有可用模型，配置详见 `config/llm/providers.json`


## ⚙️ 六、配置说明

### 配置优先级

项目支持多层级配置系统，优先级从高到低：

1. **当前目录 `.env` 文件** - 项目特定的环境变量和API密钥
2. **项目级配置** (`<project>/.iris/`) - 项目特定的配置文件和设置
3. **用户级配置** (`~/.iris/`) - 全局用户配置，所有项目共享
4. **内置默认配置** - 打包在程序中的默认配置（兜底）

### 配置目录结构

首次运行会自动创建用户级配置目录 `~/.iris/`（Windows: `C:\Users\<你>\.iris\`），包含：

```
~/.iris/
├── .env              # 全局API密钥配置
├── .env.example      # 配置模板
├── config.toml       # 全局配置文件
├── llm/              # LLM模型配置
├── agents/           # Agent配置
├── tools/            # 工具配置
└── sessions/         # 会话数据
```

项目级配置（可选）：在项目根目录创建 `.iris/` 目录可覆盖全局配置。

### 核心配置项

| 配置项 | 说明 | 示例 | 必需 |
|--------|------|------|------|
| `ZHIPU_API_KEY` | 智谱AI API密钥 | `abcd1234.efgh5678...` | ✅ 二选一 |
| `OPENAI_API_KEY` | OpenAI API密钥 | `sk-xxxxxxxx...` | ✅ 二选一 |
| `OLLAMA_BASE_URL` | Ollama服务地址 | `http://localhost:11434` | ❌ |
| `DEFAULT_LLM_PROVIDER` | 默认提供商 | `zhipu` / `openai` / `ollama` | ❌ |
| `DEFAULT_LLM_MODEL` | 默认模型 | `glm-4.7-flash` / `gpt-4o-mini` | ❌ |
| `DIFY_API_KEY` | Dify云端API密钥 | `app-xxxxxxxx...` | ❌ |
| `TAVILY_API_KEY` | Tavily搜索API密钥 | `tvly-xxxxxxxx...` | ❌ 推荐 |
| `AMAP_API_KEY` | 高德地图API密钥 | `xxxxxxxx...` | ❌ 推荐 |
| `NOTION_TOKEN` | Notion集成Token | `ntn_xxxxxxxx...` | ❌ |

### 高级配置

#### LLM模型配置

位置：`~/.iris/llm/models/providers.json`（或项目级 `.iris/llm/models/providers.json`）

- **模型参数覆盖**: `mode_overrides` 字段可针对不同模式设置不同参数
- **温度固定**: 部分模型（如GPT-5）的温度参数固定，无法通过配置修改
- **工具支持**: `supports_tools` 字段控制模型是否启用工具调用

#### DeepAgent配置

位置：`~/.iris/agents/deep/models/`（或项目级 `.iris/agents/deep/models/`）

- 主代理配置：`mainagents.json`
- 子代理配置：`subagents.json`
- 中间件配置：`middleware/` 目录

#### 配置覆盖策略

- **全局配置**: 修改 `~/.iris/` 下的配置文件，影响所有项目
- **项目配置**: 在项目根目录创建 `.iris/` 并放置配置文件，仅影响当前项目
- **临时配置**: 在当前目录创建 `.env` 文件，覆盖环境变量

详细配置说明请参考：
- 安装指南：[IRIS_SETUP.md](IRIS_SETUP.md)
- 配置模板：`~/.iris/.env.example`
- 内置默认配置：打包在程序中自动加载

> **💡 配置热重载**: 修改配置文件后，使用 `/reload` 命令即可生效，无需重启程序

## 📝 七、更新日志

完整更新历史请查看 [CHANGELOG.md](CHANGELOG.md)
