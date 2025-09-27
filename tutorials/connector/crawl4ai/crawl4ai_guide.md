# Crawl4AI 连接器开发与使用指南 🚀

## 1. 概述 📚

Crawl4AI 连接器是一个基于 HTTP 的网络爬虫工具，它通过与 Crawl4AI Docker 服务交互，为 AI 代理提供高质量的网页内容提取功能。该连接器专为 LLM（大型语言模型）应用优化，能够将网页内容转换为干净、结构化的 Markdown 格式，适用于 RAG（检索增强生成）和 AI 代理应用。

### 核心特性 ✨
- **异步 HTTP 客户端**：基于 httpx 构建，支持连接池和重试机制
- **灵活配置**：通过 JSON 配置文件和环境变量管理参数
- **流式处理**：支持同步和流式爬取两种模式
- **错误处理**：完善的异常处理和重试策略
- **AI 代理集成**：与 LangChain 工具系统完美集成

## 2. 架构设计 🏗️

### 2.1 文件结构
```
src/tools/connector/crawl4ai/
├── __init__.py           # 工具初始化和注册
├── adapter.py           # LangChain 工具适配器
├── client.py            # HTTP 客户端实现
├── config.py            # 配置管理
├── errors.py            # 异常定义
└── utils.py (可选)      # 辅助函数
```

### 2.2 模块职责

#### 2.2.1 配置模块 (`config.py`)
- 从 JSON 配置文件加载基础设置（基础 URL、超时时间、认证令牌）
- 支持环境变量覆盖（`CRAWL4AI_BASE_URL`、`CRAWL4AI_TIMEOUT`、`CRAWL4AI_TOKEN`）
- 加载 30 多个 Crawl4AI 专用参数，包括内容过滤、页面加载和性能设置
- 提供默认值回退机制

#### 2.2.2 客户端模块 (`client.py`)
- 基于 `httpx.AsyncClient` 的异步 HTTP 封装
- 设置 `trust_env=False` 避免代理干扰
- 实现重试和退避策略以处理临时故障
- 提供 `health_check()`、`get_schema()`、`crawl()`（同步）、`crawl_stream()`（NDJSON）方法
- 映射 HTTP/网络错误到连接器异常以提供更清晰的代理消息

#### 2.2.3 适配器模块 (`adapter.py`)
- 定义 LangChain `BaseTool` 子类（`Crawl4AICrawlTool`、`Crawl4AIStreamTool`）
- 验证综合输入（30 多个参数）并委托给客户端
- 返回标准化的字典响应（Markdown、元数据、可选的 Base64 编码二进制负载）
- 支持运行时参数覆盖，优先于配置默认值

#### 2.2.4 异常模块 (`errors.py`)
- 提供 `Crawl4AIConnectorError` 基异常类
- 定义 `Crawl4AIHTTPError` 用于 HTTP 相关错误

## 3. API 接口 🌐

### 3.1 HTTP API 表面

Crawl4AI Docker 服务提供以下 REST 端点：

| 端点 | 方法 | 用途 | 说明 |
|------|------|------|------|
| `/health` | GET | 服务健康检查 | 用于连接器就绪探测 |
| `/schema` | GET | 可用配置/工具的 Schema | 用于验证 |
| `/crawl` | POST | 同步爬取 | 请求体包含 `urls`、`browser_config`、`crawler_config` |
| `/crawl/stream` | POST | 流式爬取（NDJSON） | 以包含 `status: "completed"` 的记录终止 |
| `/html` | POST | 预处理 HTML 提取 | 请求体：`{ "url": "..." }` |
| `/screenshot` | POST | 全页截图 | 支持 `screenshot_wait_for`、`output_path` |
| `/pdf` | POST | PDF 导出 | 支持 `output_path` |
| `/execute_js` | POST | 运行 JS 片段 | 请求体包含 `scripts` 数组 |

### 3.2 Python API

#### 3.2.1 Crawl4AICrawlTool
- **工具名称**: `crawl4ai_crawl`
- **描述**: 同步爬取网页并返回结构化 Markdown 内容
- **参数**:
  - `urls`: 要爬取的 URL 列表
  - `word_count_threshold`: 内容处理前的最小字数阈值
  - `only_text`: 是否仅提取纯文本内容
  - `css_selector`: CSS 选择器，用于提取页面特定部分
  - `target_elements`: 用于 Markdown 生成的特定元素 CSS 选择器列表
  - `excluded_tags`: 从处理中排除的 HTML 标签列表
  - `excluded_selector`: 从处理中排除的 CSS 选择器
  - `remove_forms`: 是否移除所有 `<form>` 元素
  - `prettiify`: 是否应用 fast_format_html 生成格式化 HTML 输出
  - `parser_type`: HTML 解析器类型，默认为 lxml
  - `wait_until`: 页面导航时等待的条件（如 domcontentloaded）
  - `page_timeout`: 页面操作超时时间（毫秒）
  - `wait_for`: 等待内容提取前的 CSS 选择器或 JS 条件
  - `wait_for_timeout`: `wait_for` 条件的特定超时时间（毫秒）
  - `delay_before_return_html`: 检索最终 HTML 前的延迟时间（秒）
  - `scan_full_page`: 是否滚动整个页面以加载所有内容
  - `scroll_delay`: 如果 `scan_full_page` 为 True，则在滚动步骤之间的延迟时间（秒）
  - `process_iframes`: 是否处理和内联 iframe 内容
  - `remove_overlay_elements`: 是否在提取 HTML 前移除覆盖层/弹窗
  - `simulate_user`: 是否模拟用户交互以对抗反爬虫措施
  - `screenshot`: 是否在爬取后截图
  - `screenshot_wait_for`: 截图前的额外等待时间
  - `pdf`: 是否生成页面 PDF
  - `exclude_external_images`: 是否排除所有外部图片
  - `exclude_all_images`: 是否排除所有图片
  - `table_score_threshold`: 处理表格的最小分数阈值
  - `cache_mode`: 缓存处理方式：enabled、bypass、disabled、read_only、write_only
  - `exclude_external_links`: 是否排除结果中的所有外部链接
  - `exclude_social_media_links`: 是否排除指向社交媒体域名的链接
  - `exclude_domains`: 要从结果中排除的特定域名列表
  - `verbose`: 启用详细日志
  - `js_code`: 在页面上运行的 JavaScript 代码/片段
  - `wait_for_images`: 是否等待图片加载后再提取内容
  - `ignore_body_visibility`: 是否忽略 body 可见性再继续
  - `max_scroll_steps`: 全页扫描时执行的最大滚动步骤数
  - `override_navigator`: 是否覆盖导航器属性以实现更人性化的行为
  - `magic`: 是否自动处理覆盖层/弹窗
  - `adjust_viewport_to_content`: 是否根据页面内容维度调整视口
  - `browser_config`: 浏览器配置
  - `crawler_config`: 爬虫配置

#### 3.2.2 Crawl4AIStreamTool
- **工具名称**: `crawl4ai_stream`
- **描述**: 流式爬取网页并返回结构化 Markdown 内容
- **参数**: 与 `Crawl4AICrawlTool` 相同

## 4. 配置系统 ⚙️

### 4.1 配置文件结构

Crawl4AI 连接器支持分层配置系统，优先级从高到低：

1. **API 调用参数**：运行时传入的参数
2. **环境变量**：以 `CRAWL4AI_` 开头的环境变量
3. **JSON 配置文件**：`config/connector/crawl4ai/config.json`
4. **默认值**：代码中的默认配置

### 4.2 JSON 配置示例

```
{
    "default": {
      "base_url": "http://localhost:11235",
      "timeout": 60,
      "stream_timeout": 120,
      "retry_attempts": 2,
      "token": null
    },
    "crawl": {
      "word_count_threshold": 200,
      "only_text": true,
      "css_selector": null,
      "target_elements": [],
      "excluded_tags": ["nav", "footer", "aside", "script", "style"],
      "excluded_selector": "",
      "remove_forms": false,
      "prettiify": false,
      "parser_type": "lxml",
      "wait_until": "domcontentloaded",
      "page_timeout": 60000,
      "wait_for": null,
      "wait_for_timeout": null,
      "delay_before_return_html": 0.1,
      "scan_full_page": false,
      "scroll_delay": 0.2,
      "process_iframes": false,
      "remove_overlay_elements": false,
      "simulate_user": false,
      "screenshot": false,
      "screenshot_wait_for": null,
      "pdf": false,
      "exclude_external_images": false,
      "exclude_all_images": false,
      "table_score_threshold": 7,
      "cache_mode": "bypass",
      "exclude_external_links": false,
      "exclude_social_media_links": false,
      "exclude_domains": [],
      "verbose": true,
      "mean_delay": 0.1,
      "max_range": 0.3,
      "semaphore_count": 5,
      "js_code": null,
      "wait_for_images": false,
      "ignore_body_visibility": true,
      "max_scroll_steps": null,
      "override_navigator": false,
      "magic": false,
      "adjust_viewport_to_content": false,
      "capture_mhtml": false,
      "image_description_min_word_threshold": 50,
      "image_score_threshold": 5,
      "exclude_internal_links": false,
      "score_links": false,
      "log_console": false,
      "capture_network_requests": false,
      "capture_console_messages": false,
      "method": "GET",
      "check_robots_txt": false,
      "keep_data_attributes": false,
      "keep_attrs": [],
      "scraping_strategy": null,
      "proxy_config": null,
      "locale": null,
      "timezone_id": null,
      "geolocation": null,
      "fetch_ssl_certificate": false,
      "session_id": null,
      "shared_data": null,
      "js_only": false,
      "stream": false,
      "user_agent": null,
      "user_agent_mode": null,
      "deep_crawl_strategy": null,
      "link_preview_config": null,
      "url_matcher": null,
      "match_mode": "or"
    }
  }
```

### 4.3 配置参数详解

#### 4.3.1 内容处理参数
- `word_count_threshold`: 内容处理前的最小字数阈值
- `only_text`: 尽可能提取纯文本内容
- `css_selector`: CSS 选择器提取页面特定部分
- `target_elements`: 特定元素的 CSS 选择器列表
- `excluded_tags`: 从处理中排除的 HTML 标签（如 `["nav", "footer", "aside", "script", "style"]`）
- `remove_forms`: 从 HTML 中移除 `<form>` 元素

#### 4.3.2 浏览器和页面参数
- `wait_until`: 页面加载完成的条件（"domcontentloaded"、"load"、"networkidle"）
- `page_timeout`: 页面操作超时时间（毫秒）
- `locale`: 浏览器上下文的语言环境
- `timezone_id`: 时区标识符

#### 4.3.3 内容和交互参数
- `scan_full_page`: 滚动整个页面以加载所有内容
- `process_iframes`: 处理和内联 iframe 内容
- `remove_overlay_elements`: 提取 HTML 前移除覆盖层/弹窗
- `simulate_user`: 模拟用户交互以绕过反爬虫措施
- `js_code`: 在页面上执行的 JavaScript 代码
- `wait_for`: 等待的 CSS 选择器或 JS 条件

#### 4.3.4 媒体处理参数
- `screenshot`: 爬取后截图
- `pdf`: 生成页面 PDF
- `exclude_external_images`: 从处理中排除外部图片

#### 4.3.5 缓存和性能参数
- `cache_mode`: 缓存行为（"enabled"、"bypass"、"disabled"、"read_only"、"write_only"）
- `semaphore_count`: 允许的并发操作数

#### 4.3.6 链接和域名参数
- `exclude_external_links`: 从结果中排除外部链接
- `exclude_social_media_links`: 排除社交媒体域名链接
- `exclude_domains`: 要排除的特定域名列表

## 5. 错误处理 🛡️

### 5.1 异常层次结构
- `Crawl4AIConnectorError`：Crawl4AI 连接器错误的基异常
- `Crawl4AIHTTPError`：HTTP 相关错误，包含状态码

### 5.2 错误处理策略
- **超时**: `/crawl` 60秒，`/crawl/stream` 120秒；可通过环境变量配置
- **重试**: 对连接错误和 502/503 响应的有限指数退避
- **用户友好错误**: 将 HTTP 状态码映射为简洁消息（401 → 认证必需，504 → 爬虫超时等）
- **客户端初始化验证**: 确保客户端通过异步上下文管理器初始化

### 5.3 健康检查机制
连接器实现健康检查功能，验证 Crawl4AI 服务是否正常运行：

```python
async def health_check(self) -> bool:
    """检查 Crawl4AI 服务是否健康"""
    try:
        result = await self._make_request("GET", "/health")
        return result.get("status") == "ok"
    except Exception:
        return False
```

## 6. 与 AI 代理连接 🔗

### 6.1 工具注册系统
Crawl4AI 连接器通过 `ConnectorToolManager` 与 AI 代理集成：

- **工具管理**: 实现类似于 `SDKToolManager` 的 API（`get_all_tools()`、`get_tool_by_name()`、`get_tools_info()`）
- **源标记**: 应用源标记，如 `tool.metadata = {"source": "connector.crawl4ai"}` 用于下游过滤
- **CLI 集成**: 通过 `:connector status` 和 `:connector tools` 命令提供状态和工具列表信息

### 6.2 代理集成实现
1. `src/tools/__init__.py` 导入 `ConnectorToolManager`，与 SDK/MCP 并列
2. 修改代理的 `_load_tools()` 方法（`OpenAIAgent`、`OllamaAgent`、`ZhipuAgent` 等）在 SDK 和 MCP 工具后附加连接器工具
3. 确保工具元数据包含 `source="connector.crawl4ai"` 用于日志/分析
4. 在代理文档中提供简短的提示指导：何时调用 Crawl4AI（实时网站内容、截图、PDF、JS 执行）

### 6.3 CLI 集成
- 引入 `src/components/connector_control.py`，仿照 `mcp_control.py` 但简化：
  - `connector_status(verbose: bool = False)` → 运行健康检查，返回工具计数和基础 URL
  - `connector_tools(json_flag: bool = False)` → 列出注册的连接器工具，包含名称和描述
- 扩展 CLI 解析器（如 `src/components/cli.py`）添加 `:connector status` 和 `:connector tools` 命令
- 命令依赖 `ConnectorToolManager` 获取数据；健康检查访问 `/health` 并报告通过/失败

## 7. 使用方法 💡

### 7.1 基本使用
```python
from src.tools.connector.crawl4ai import get_tools

# 获取所有 Crawl4AI 工具
tools = get_tools()

# 使用爬取工具
crawl_tool = tools[0]  # Crawl4AICrawlTool
result = await crawl_tool._arun(urls=["https://example.com"], only_text=True)
```

### 7.2 配置连接器
1. 复制示例配置文件：
   ```bash
   cp config/connector/crawl4ai/config_example.json config/connector/crawl4ai/config.json
   ```

2. 修改 `base_url` 指向您的 Crawl4AI 服务地址

3. 根据需要调整其他参数

### 7.3 环境变量配置
- `CRAWL4AI_BASE_URL`: Crawl4AI 服务的基础 URL
- `CRAWL4AI_TIMEOUT`: 请求超时时间（秒）
- `CRAWL4AI_STREAM_TIMEOUT`: 流式请求超时时间（秒）
- `CRAWL4AI_TOKEN`: 认证令牌
- `CRAWL4AI_RETRY_ATTEMPTS`: 重试次数

## 8. 最佳实践 🎯

### 8.1 LLM 友好内容提取
配置系统启用最佳 LLM 友好内容提取：
- 通过 `only_text: true` 过滤获取干净的文本内容
- 通过 `excluded_tags` 过滤元素，排除导航、广告和非内容元素
- 通过 `java_script_enabled: true` 启用 JavaScript 支持以加载动态内容
- 通过 `wait_for` 设置等待条件，确保内容在提取前完全加载
- 通过 `scan_full_page: true` 支持单页应用程序的全页滚动

### 8.2 性能优化
- 合理设置超时时间，避免长时间等待
- 使用缓存模式减少重复请求
- 根据需要启用/禁用媒体处理

## 9. 测试考虑 🧪

- `ConnectorToolManager` 的单元测试，验证标记和信息摘要
- CLI 测试，覆盖成功和失败场景下的 `:connector status` 和 `:connector tools` 命令输出
- 集成测试，验证正确配置加载和参数应用

## 10. 未来增强 🚀

- 可选 JWT 流程（`POST /token` 然后 Bearer 头），一旦启用安全功能
- 复杂提取策略的高级预设（AI 辅助、余弦过滤、JS 任务）
- 大型资产的文件持久化钩子（截图/PDF），如果代理需要文件系统工件
- 当需要更高可靠性或长时间运行任务时，使用异步 `/crawl/job` 轮询工具

---

本指南记录了已实现的连接器系统，提供了用于优化 LLM 友好内容提取的全面配置选项。