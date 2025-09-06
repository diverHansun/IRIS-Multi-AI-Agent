# MCP 工具使用指南

Model Context Protocol (MCP) 是一种标准化协议，允许 AI Agent 与各种工具和服务进行交互。本项目集成了多个 MCP 服务器，扩展了 Agent 的能力。

## MCP 文件夹作用

### 配置文件 (`config/` 目录)
`config/` 目录下的 MCP 配置文件用于管理各种 MCP 服务器的连接和工具。主要文件包括：

- `mcp.toml`: 主配置文件，定义启用的 MCP 服务器及其参数
- `mcp.toml.example`: 配置示例文件，展示各种 MCP 服务器的配置方法

### 核心代码 (`src/MCP/` 目录)
`src/MCP/` 目录包含了 MCP 系统的核心实现代码，提供完整的 MCP 服务器管理和工具集成功能：

#### 主要模块说明

1. **`manager.py`** - 全局 MCP 管理器
   - 实现 `GlobalMCPManager` 单例类，管理所有 MCP 服务器
   - 负责服务器启动、工具聚合、状态监控
   - 提供异步初始化和配置重载功能
   - 支持优雅的错误处理和依赖检查

2. **`config_loader.py`** - 配置加载器
   - 支持 TOML 和 JSON 格式的配置文件
   - 自动环境变量展开（`$VAR` 格式）
   - 配置验证和默认值处理
   - 支持配置文件路径自动发现

3. **`tool_adapter.py`** - 工具适配器
   - 工具命名策略实现（前缀、过滤等）
   - 工具名称规范化（符合 OpenAI 函数命名规则）
   - 工具模式摘要生成，用于 CLI 显示
   - 支持工具包含/排除过滤

4. **`types.py`** - 类型定义
   - `MCPConfig`: 主配置数据结构
   - `ServerConfig`: 单个服务器配置
   - `RetryConfig`: 重试策略配置
   - 提供类型安全的数据结构

5. **`errors.py`** - 异常定义
   - `MCPConfigError`: 配置错误
   - `MCPNotAvailableError`: 依赖不可用错误
   - `MCPInitializationError`: 初始化错误
   - 提供清晰的错误分类和处理

#### 核心功能特性

- **单例模式**: 确保全局只有一个 MCP 管理器实例
- **异步支持**: 完全异步的服务器管理和工具调用
- **容错机制**: 优雅处理依赖缺失和服务器启动失败
- **配置热重载**: 支持运行时重新加载配置
- **工具聚合**: 将多个 MCP 服务器的工具统一管理
- **命名空间**: 支持工具名称前缀和过滤策略
- **状态监控**: 提供详细的服务器和工具状态信息

## 支持的 MCP 服务器

### 1. Fetch MCP
用于从 URL 获取网页内容
- 工具名称前缀: `fetch:`
- 主要功能: 网页内容抓取

### 2. Filesystem MCP
用于读取本地文件系统
- 工具名称前缀: `fs:`
- 主要功能: 文件读取、目录浏览

### 3. Notion MCP
用于与 Notion 页面和数据库交互
- 工具名称前缀: `notion:`
- 主要功能: 页面查询、数据库操作

## 安装 MCP 服务器

### 方法 1: 全局安装 (推荐)
使用 npm 全局安装 MCP 服务器，这样可以在任何位置使用：

```bash
# 安装 Fetch MCP 服务器
npm install -g @modelcontextprotocol/server-fetch

# 安装 Filesystem MCP 服务器
npm install -g @modelcontextprotocol/server-filesystem

# 安装 Notion MCP 服务器
npm install -g notion-mcp
```

### 方法 2: 使用 npx (无需预先安装)
直接使用 npx 运行，无需预先安装：

```bash
# 运行 Fetch MCP 服务器
npx -y @modelcontextprotocol/server-fetch

# 运行 Filesystem MCP 服务器
npx -y @modelcontextprotocol/server-filesystem

# 运行 Notion MCP 服务器
npx -y notion-mcp
```

## 配置 MCP 服务器

MCP 服务器通过 `config/mcp.toml` 文件配置。以下是示例配置：

```toml
enabled = true
auto_start = true
prefer_mcp = true
namespace_strategy = "prefix"
default_prefix = "mcp_"

# Fetch MCP 配置
[servers.fetch]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-fetch"]
rename_prefix = "fetch:"

# Filesystem MCP 配置
[servers.filesystem]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "--root", "./data"]
rename_prefix = "fs:"

# Notion MCP 配置
[servers.notion]
transport = "stdio"
command = "npx"
args = ["-y", "notion-mcp"]
rename_prefix = "notion:"

[servers.notion.env]
NOTION_CLIENT_ID = "$NOTION_CLIENT_ID"
NOTION_CLIENT_SECRET = "$NOTION_CLIENT_SECRET"
NOTION_REDIRECT_URI = "$NOTION_REDIRECT_URI"
```

## 使用 MCP 工具

在 Agent 模式下，MCP 工具会自动加载。您可以通过以下 CLI 命令管理 MCP：

- `mcp status [-v]`: 查看 MCP 状态和工具信息
- `mcp tools [--json]`: 列出所有可用的 MCP 工具
- `mcp reload`: 重新加载 MCP 配置

### Fetch MCP 使用示例

```json
{
  "name": "mcp_fetch-fetch",
  "arguments": {
    "url": "https://example.com"
  }
}
```

### Filesystem MCP 使用示例

```json
{
  "name": "mcp_fs-read-file",
  "arguments": {
    "path": "data/example.txt"
  }
}
```

### Notion MCP 使用示例

```json
{
  "name": "mcp_notion-search",
  "arguments": {
    "query": "项目计划"
  }
}
```

## 工具参数说明

### Fetch MCP
1. `fetch`: 从 URL 获取内容
   - `url` (string, required): 要获取的 URL
   - `method` (string, optional): HTTP 方法，默认为 "GET"
   - `headers` (object, optional): 请求头
   - `body` (string, optional): 请求体

### Filesystem MCP
1. `read-file`: 读取文件内容
   - `path` (string, required): 文件路径
2. `list-directory`: 列出目录内容
   - `path` (string, required): 目录路径

### Notion MCP
1. `search`: 搜索 Notion 页面
   - `query` (string, required): 搜索关键词
2. `get-page`: 获取页面内容
   - `page_id` (string, required): 页面 ID

## 注意事项

1. 确保系统已安装 Node.js 和 npm (版本 16+)
2. 网络连接正常，能够访问目标服务
3. 遵守各服务的使用条款和限制
4. Filesystem MCP 限制访问目录为项目内的 `./data` 文件夹
5. Notion MCP 需要配置 OAuth 凭据

## 故障排查

### 常见问题

1. **npx 命令找不到**:
   - 检查 Node.js 和 npm 是否正确安装
   - 确认 PATH 环境变量包含 npm 路径

2. **MCP 工具无法使用**:
   - 运行 `mcp status -v` 查看详细状态
   - 检查 `config/mcp.toml` 配置是否正确
   - 确认 MCP 服务器命令可以正常执行

3. **Notion MCP 认证失败**:
   - 检查环境变量中的 Notion 凭据
   - 确认 OAuth 配置正确
   - 首次使用需要完成 OAuth 授权流程

### 调试命令

```bash
# 查看 MCP 状态
mcp status

# 查看详细状态（包括工具参数）
mcp status -v

# 列出所有 MCP 工具
mcp tools

# 重新加载配置
mcp reload
```