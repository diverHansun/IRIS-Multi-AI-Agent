# Crawl4AI 连接器配置指南

本文档介绍了 Crawl4AI 连接器可用的配置选项，该连接器与 Crawl4AI Docker 服务进行交互。

## 概述

Crawl4AI 连接器提供对 Crawl4AI Docker 服务 API 的访问，该服务提供专为 LLM 使用优化的高级网络爬虫功能。连接器允许您配置浏览器和爬虫行为，以获得用于 RAG（检索增强生成）和 AI 代理的干净、结构化内容。

## 配置结构

连接器配置通过以下文件组织：

- `config_example.json`: 示例配置文件，包含所有可用参数的默认值
- `config.json`: 实际运行时使用的配置文件（需要用户自行创建）

配置文件包含两个主要部分：

- `default`: 基本连接和常规设置
- `crawl`: 详细的爬虫行为参数

### 配置设置步骤

1. 复制 `config_example.json` 为 `config.json`
2. 根据您的需求修改 `config.json` 中的参数
3. `config.json` 文件加入 `.gitignore`，不会被提交到版本控制

## 默认配置参数

这些参数控制与 Crawl4AI 服务的基本连接：

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `base_url` | string | `"http://localhost:11235"` | Crawl4AI Docker 服务的 URL |
| `timeout` | int | `60` | 请求超时时间（秒） |
| `stream_timeout` | int | `120` | 流式请求超时时间（秒） |
| `retry_attempts` | int | `2` | 失败请求的重试次数 |
| `token` | string or null | `null` | 认证令牌（如需要） |

## 爬虫特定参数

这些参数控制爬虫过程和内容提取的行为：

### 核心爬虫配置
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `word_count_threshold` | int | `200` | 处理内容前的最小词数阈值 |
| `only_text` | boolean | `true` | 尽可能提取纯文本内容 |
| `css_selector` | string or null | `null` | 提取页面特定部分的 CSS 选择器 |
| `target_elements` | array | `[]` | 要提取的特定元素的 CSS 选择器列表 |
| `excluded_tags` | array | `["nav", "footer", "aside", "script", "style"]` | 要从处理中排除的 HTML 标签 |
| `excluded_selector` | string | `""` | 要从处理中排除的 CSS 选择器 |
| `remove_forms` | boolean | `false` | 从 HTML 中移除 `<form>` 元素 |
| `prettiify` | boolean | `false` | 美化 HTML 输出 |

### 浏览器和页面配置
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `browser_type` | string | `"chromium"` | 使用的浏览器："chromium"、"firefox"、"webkit" |
| `headless` | boolean | `true` | 以无头模式运行浏览器 |
| `ignore_https_errors` | boolean | `true` | 忽略 HTTPS 证书错误 |
| `java_script_enabled` | boolean | `true` | 启用 JavaScript 执行 |
| `wait_until` | string | `"domcontentloaded"` | 何时认为页面已加载："domcontentloaded"、"load"、"networkidle" |
| `page_timeout` | int | `60000` | 页面操作超时时间（毫秒） |
| `locale` | string or null | `null` | 浏览器上下文的语言环境（如 "en-US"） |
| `timezone_id` | string or null | `null` | 时区标识符（如 "America/New_York"） |

### 内容和交互配置
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `scan_full_page` | boolean | `false` | 滚动整个页面以加载所有内容 |
| `scroll_delay` | float | `0.2` | 滚动步骤之间的延迟（秒） |
| `process_iframes` | boolean | `false` | 处理并内联 iframe 内容 |
| `remove_overlay_elements` | boolean | `false` | 在提取 HTML 前移除覆盖层/弹窗 |
| `simulate_user` | boolean | `false` | 模拟用户交互以绕过反机器人措施 |
| `js_code` | string/array or null | `null` | 在页面上执行的 JavaScript 代码 |
| `wait_for` | string or null | `null` | 等待的 CSS 选择器或 JS 条件 |
| `wait_for_timeout` | int or null | `null` | wait_for 条件的超时时间 |

### 媒体处理配置
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `screenshot` | boolean | `false` | 爬虫后截图 |
| `screenshot_wait_for` | float or null | `null` | 截图前的等待时间 |
| `pdf` | boolean | `false` | 生成页面的 PDF |
| `image_score_threshold` | int | `5` | 处理图像的最小分数 |
| `exclude_external_images` | boolean | `false` | 排除外部图像的处理 |
| `exclude_all_images` | boolean | `false` | 排除所有图像的处理 |

### 缓存和性能配置
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `cache_mode` | string | `"bypass"` | 缓存行为："enabled"、"bypass"、"disabled"、"read_only"、"write_only" |
| `mean_delay` | float | `0.1` | 爬取多个 URL 时请求间的基础延迟 |
| `max_range` | float | `0.3` | 最大随机附加延迟范围 |
| `semaphore_count` | int | `5` | 允许的并发操作数 |

### 链接和域名配置
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `exclude_external_links` | boolean | `false` | 从结果中排除外部链接 |
| `exclude_social_media_links` | boolean | `false` | 排除社交媒体域名链接 |
| `exclude_domains` | array | `[]` | 要排除的特定域名 |
| `score_links` | boolean | `false` | 计算链接的质量分数 |

### 返回格式配置
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `return_format` | string | `"markdown"` | 返回格式："markdown" 返回清理后的markdown内容，"json" 返回完整的结构化数据 |

### LLM 优化参数

这些参数专为 LLM 使用场景优化，提供更精准的内容过滤和提取：

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `content_filter_type` | string or null | `null` | 内容过滤器类型："pruning"、"bm25" 或 "none" |
| `pruning_threshold` | float or null | `null` | pruning 过滤器的内容保留阈值 (0-1) |
| `pruning_threshold_type` | string or null | `null` | 阈值类型："fixed" 或 "dynamic" |
| `min_word_threshold` | int or null | `null` | 内容块的最小词数要求 |
| `bm25_threshold` | float or null | `null` | BM25 相关性阈值 |
| `user_query` | string or null | `null` | BM25 内容过滤的查询关键词 |
| `max_token_length` | int or null | `null` | LLM 处理的最大 token 长度 |
| `prefer_fit_markdown` | boolean or null | `null` | 优先使用 fit_markdown 而非 raw_markdown |
| `extract_main_content` | boolean or null | `null` | 仅提取主要内容区域 |

## 示例配置

完整的配置示例请参考 `config_example.json` 文件，该文件包含了所有可用参数的默认值。

以下是一个常用的自定义配置示例：

```json
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
    "excluded_tags": ["nav", "footer", "aside", "script", "style", "header"],
    "remove_forms": true,
    "wait_until": "domcontentloaded",
    "page_timeout": 60000,
    "scan_full_page": false,
    "process_iframes": false,
    "remove_overlay_elements": true,
    "simulate_user": false,
    "screenshot": false,
    "pdf": false,
    "exclude_external_images": true,
    "cache_mode": "bypass",
    "exclude_external_links": true,
    "verbose": true
  }
}
```

### LLM 优化配置示例

针对 LLM 使用场景的优化配置：

```json
{
  "default": {
    "base_url": "http://localhost:11235",
    "timeout": 90,
    "stream_timeout": 180,
    "retry_attempts": 3
  },
  "crawl": {
    "word_count_threshold": 100,
    "only_text": true,
    "excluded_tags": ["nav", "footer", "aside", "script", "style", "header", "advertisement"],
    "remove_forms": true,
    "content_filter_type": "pruning",
    "pruning_threshold": 0.48,
    "pruning_threshold_type": "fixed",
    "min_word_threshold": 30,
    "prefer_fit_markdown": true,
    "extract_main_content": true,
    "max_token_length": 100000,
    "wait_until": "domcontentloaded",
    "page_timeout": 60000,
    "remove_overlay_elements": true,
    "exclude_all_images": true,
    "exclude_external_links": true,
    "cache_mode": "enabled",
    "return_format": "markdown"
  }
}
```

> **注意**: 实际使用时请复制 `config_example.json` 为 `config.json` 并根据需要调整参数。

## 运行时使用参数

在调用 `crawl4ai_crawl` 或 `crawl4ai_stream` 工具时，您可以覆盖特定参数：

```python
# 使用自定义参数的示例调用
result = await crawl4ai_crawl(
    urls=["https://example.com"],
    only_text=True,
    excluded_tags=["nav", "footer", "advertisement"],
    wait_for="#content",
    scan_full_page=True
)
```

## LLM 就绪内容的最佳实践

为了获得最佳的 LLM 就绪内容提取：

### 基础优化
1. **内容过滤**: 启用 `only_text: true` 以获得干净的文本内容
2. **元素移除**: 使用 `excluded_tags` 排除导航、广告和其他非内容元素
3. **JavaScript**: 保持 `java_script_enabled: true` 以加载动态内容
4. **等待条件**: 使用 `wait_for` 确保内容在提取前完全加载
5. **全页滚动**: 对单页应用程序或无限滚动内容启用 `scan_full_page: true`

### 高级 LLM 优化
6. **智能过滤**: 使用 `content_filter_type: "pruning"` 自动移除低质量内容
7. **内容质量控制**: 设置 `pruning_threshold: 0.48` 保留高质量内容
8. **主要内容提取**: 启用 `extract_main_content: true` 专注于核心内容
9. **Markdown 优化**: 设置 `prefer_fit_markdown: true` 获取结构化的内容
10. **Token 限制**: 配置 `max_token_length` 控制内容长度
11. **查询相关过滤**: 使用 `content_filter_type: "bm25"` 和 `user_query` 获取相关内容
12. **返回格式选择**: 设置 `return_format: "markdown"` 获取LLM友好的文本，或 `"json"` 获取完整结构化数据

### 内容过滤策略
- **Pruning 过滤器**: 基于内容密度、链接密度和标签重要性自动筛选
- **BM25 过滤器**: 基于查询关键词的相关性排序和过滤
- **混合策略**: 先使用 pruning 移除噪音，再用 BM25 提取相关内容

## 故障排除

### 常见问题：

- **超时错误**: 增加 `crawler_config` 中的 `page_timeout` 或 `default` 中的 `timeout`
- **JavaScript 未执行**: 确保 `java_script_enabled: true` 和适当的 `wait_until`
- **动态内容未加载**: 使用 `wait_for` 参数等待特定元素
- **性能问题**: 调整 `semaphore_count` 和缓存设置
- **返回格式问题**: 检查 `return_format` 设置，`"markdown"` 返回清理后的文本，`"json"` 返回完整数据

### 验证配置：

您可以通过访问 Crawl4AI 服务的 `/schema` 端点来检查当前配置：
```
GET http://localhost:11235/schema
```

这将返回服务器中的默认 `BrowserConfig` 和 `CrawlerRunConfig` 配置。

## 快速开始

### 1. 创建配置文件

```bash
# 复制示例配置文件
cp config/connector/crawl4ai/config_example.json config/connector/crawl4ai/config.json
```

### 2. 编辑配置文件

根据您的需求修改 `config.json` 中的参数。常用的修改包括：

- 修改 `base_url` 以指向您的 Crawl4AI 服务地址
- 调整 `timeout` 和 `page_timeout` 以适应您的网络环境
- 根据需要启用/禁用 `screenshot`、`pdf` 等功能

### 3. 验证配置

启动 Crawl4AI 服务后，可以通过以下方式验证配置：

```bash
# 检查服务是否运行
curl http://localhost:11235/schema
```

### 4. 开始使用

配置文件设置完成后，您就可以在应用程序中使用 Crawl4AI 连接器了。