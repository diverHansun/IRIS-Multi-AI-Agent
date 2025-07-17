# CLAUDE.md

这个文件为Claude Code (claude.ai/code) 提供在此代码库中工作的指导。

## 项目概述

这是一个基于LangChain和智谱AI GLM-4模型构建的中文优化AI Agent演示项目。该项目实现了以下核心功能：

- **上下文记忆系统**：基于LangChain 2025最佳实践的会话记忆管理
- **多搜索引擎集成**：支持Tavily、DuckDuckGo等多种搜索引擎
- **数学计算工具**：内置数学运算和复杂计算功能
- **会话管理**：支持多用户会话隔离和持久化存储
- **MCP协议支持**：标准化的工具调用架构

## 环境要求

- **运行环境**: Windows PowerShell 中的 .venv 虚拟环境
- **依赖管理**: 核心依赖已预装，无需运行 `pip install -r requirements.txt`
- **API密钥**: 需要智谱AI API密钥，推荐配置Tavily搜索API密钥以获得更好的搜索体验

## 快速开始

```bash
# 激活虚拟环境 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 运行交互式CLI
python main.py

# 运行异步演示
python main.py async

# 测试MCP集成
python -m src.tools.mcp_client
```

## 环境配置

项目需要智谱AI API密钥，配置在 `src/config.py` 中：

1. API密钥可通过 `.env` 文件设置（复制自 `.env.example`）
2. 配置文件中有开发用的硬编码备用方案
3. 支持多种编码格式的 `.env` 文件（UTF-8, GBK, GB2312）

环境变量：
- `ZHIPU_API_KEY`: 智谱AI API密钥（必需）
- `TAVILY_API_KEY`: Tavily搜索API密钥（推荐，提供更好的搜索体验）

## 架构概述

### 核心组件

**Agent系统** (`src/agents/zhipu_agent.py`):
- `ZhipuAgent`: 主要的agent类，基于LangChain AgentExecutor
- 集成上下文记忆系统，支持会话级别的对话记忆
- 集成多种搜索引擎（Tavily、DuckDuckGo）和数学工具
- 中文优化的提示词和响应格式

**LLM集成** (`src/llm/zhipu_llm.py`):
- `ZhipuAILLM`: LangChain兼容的包装类
- 直接API密钥注入，确保可靠的认证
- 同步/异步支持

**工具系统**:
- **数学工具** (`src/tools/math_tools.py`): `add_numbers`, `calculate_math`
- **Tavily搜索工具** (`src/tools/tavily_search_tool.py`): 高质量的AI搜索引擎（推荐）
- **通用搜索工具** (`src/tools/search_tools.py`): DuckDuckGo等备用搜索引擎
- **MCP搜索工具** (`src/tools/mcp_client.py`): 基于MCP协议的标准化网络搜索

**记忆系统** (`src/memory/`):
- **ChatMemoryManager** (`src/memory/chat_memory.py`): 统一的记忆管理器
- **ConversationBuffer** (`src/memory/conversation_buffer.py`): 对话缓冲区管理
- **MemoryStorage** (`src/memory/memory_storage.py`): 持久化存储管理

### MCP集成架构

项目使用 `langchain-mcp-adapters` 实现MCP协议集成：

1. **MCP客户端** (`src/tools/mcp_client.py`): 连接到外部MCP搜索服务器
2. **工具适配器**: 将MCP工具转换为LangChain兼容工具
3. **搜索功能**: 提供实时网络搜索能力

支持的MCP搜索服务器：
- Brave Search MCP Server (推荐)
- Web Search MCP Server (简单本地部署)
- 其他兼容MCP协议的搜索服务

## 开发模式

### 记忆系统集成

项目使用LangChain 2025最佳实践的`RunnableWithMessageHistory`模式：

```python
# 创建带记忆的Agent
agent = await build_zhipu_agent(
    enable_memory=True,
    memory_config={
        "max_messages": 20,
        "max_tokens": 4000,
        "auto_save": True
    }
)

# 使用记忆功能
result = agent.invoke("我的名字是张三", session_id="user_001")
result = agent.invoke("你记得我的名字吗？", session_id="user_001")  # 会记住
```

### 创建新工具

数学工具在 `src/tools/math_tools.py` 中定义，使用LangChain的 `@tool` 装饰器：

```python
from langchain_core.tools import tool

@tool
def your_math_tool(param: float) -> float:
    """数学工具描述"""
    # 实现逻辑
    return result
```

### Tavily搜索工具

高质量的AI搜索引擎，推荐作为主要搜索工具：

```python
from langchain_community.tools.tavily_search import TavilySearchResults

# 基础搜索
tavily_search = TavilySearchResults(
    max_results=5,
    search_depth="basic",
    include_answer=True
)

# 高级搜索
tavily_advanced = TavilySearchResults(
    max_results=10,
    search_depth="advanced",
    include_answer=True,
    include_raw_content=True
)
```

### MCP工具集成

网络搜索功能通过MCP协议集成：

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

# 配置MCP客户端
client = MultiServerMCPClient({
    "brave-search": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": "your-api-key"}
    }
})

# 获取工具并集成到agent
tools = await client.get_tools()
```

### Agent定制

Agent行为通过以下方式控制：
- 中文优化的提示词模板
- 工具选择（数学 + MCP搜索）
- 模型参数（温度、最大迭代次数等）

### 错误处理

项目实现了全面的错误处理：
- API密钥验证和友好错误信息
- 编码感知的 `.env` 文件加载
- MCP连接失败的优雅降级
- 详细的日志记录

## 核心文件

- `main.py`: CLI接口和异步演示
- `src/agents/zhipu_agent.py`: 核心agent实现（含记忆系统集成）
- `src/memory/`: 记忆系统模块
  - `chat_memory.py`: 统一记忆管理器
  - `conversation_buffer.py`: 对话缓冲区
  - `memory_storage.py`: 持久化存储
  - `memory_integration.md`: 记忆系统集成文档
- `src/tools/`: 工具系统
  - `tavily_search_tool.py`: Tavily搜索工具（推荐）
  - `search_tools.py`: 备用搜索工具
  - `math_tools.py`: 数学计算工具
  - `mcp_client.py`: MCP工具集成
- `src/config.py`: 配置管理（含硬编码备用方案）
- `src/llm/zhipu_llm.py`: 智谱AI LLM包装器

## 推荐的MCP搜索服务器

### 1. Brave Search MCP Server (官方推荐)
```bash
# 安装
npx -y @modelcontextprotocol/server-brave-search

# 需要Brave Search API密钥
# 在 https://api.search.brave.com/ 获取
```

### 2. 简单Web搜索MCP服务器
```bash
# 克隆项目
git clone https://github.com/mrkrsl/web-search-mcp.git
cd web-search-mcp
npm install
npm run build

# 运行服务器
node dist/index.js
```

## 中文语言特性

项目专为中文环境优化：
- 中文提示词和响应格式
- 编码感知的配置加载
- 中文错误信息和用户界面
- 中文上下文的ReAct提示词和工具描述

## 项目清理建议

为实现高内聚低耦合，建议删除或重构以下文件：
- 移除复杂的多agent类型系统，保持简单统一的agent
- 简化工具管理器，直接使用LangChain工具 + MCP适配器
- 移除冗余的MCP适配器实现，使用官方 `langchain-mcp-adapters`
- 统一配置管理，移除多余的配置层

## 部署和使用

1. **激活虚拟环境**:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```

2. **配置API密钥**:
   - 复制 `.env.example` 到 `.env`
   - 设置 `ZHIPU_API_KEY=your_api_key`
   - 推荐设置 `TAVILY_API_KEY=your_tavily_key` 以获得更好的搜索体验

3. **运行项目**:
   ```bash
   python main.py
   ```

4. **与Agent交互**:
   - 提问数学问题：Agent会使用内置数学工具
   - 提问需要搜索的问题：Agent会优先使用Tavily搜索，备用DuckDuckGo搜索
   - 支持中文自然语言交互和会话记忆功能
   - 不同session_id实现多用户会话隔离

## 技术栈

- **LLM**: 智谱AI GLM-4-Plus
- **框架**: LangChain (2025最佳实践)
- **记忆系统**: RunnableWithMessageHistory + 持久化存储
- **搜索引擎**: Tavily Search API (推荐) + DuckDuckGo (备用)
- **协议**: Model Context Protocol (MCP)
- **工具**: 数学计算 + 多引擎网络搜索 + 上下文记忆
- **语言**: Python 3.8+
- **平台**: Windows (PowerShell + .venv)

## 开发指南

### 记忆系统开发

详细的记忆系统集成文档请参考：`src/memory/memory_integration.md`

### 搜索工具开发

Tavily搜索工具集成文档请参考：`src/tools/tavily_integration.md`

### 代码质量要求

- 遵循Python PEP 8标准
- 使用中文注释和文档字符串
- 实现完整的错误处理和日志记录
- 在.venv虚拟环境中测试功能