# Crawl4AI 配置参考手册

> 本文档是配置参数的快速参考手册。完整使用教程请参考 [crawl4ai_guide.md](..\..\..\tutorials\connector\crawl4ai\crawl4ai_guide.md)

## 📁 配置文件

- **config.json** - 实际使用的配置文件
- **config_example.json** - 完整配置示例(包含所有参数)
- **config.template.json** - 简化配置模板(只包含常用参数)
- **config.json.commented** - 带详细注释的配置说明

## 🔄 配置优先级

参数按以下优先级生效(从高到低):

1. **Agent 调用参数** - 运行时传递的 `browser_config` / `crawler_config` 字典
2. **config.json** - 配置文件中的设置
3. **环境变量** - `CRAWL4AI_*` 开头的环境变量
4. **默认值** - 代码中的默认配置

## 📦 配置结构

所有参数通过配置类字典传递:

| 配置字典 | 说明 | 状态 | 基于SDK类 |
|---------|------|------|----------|
| `default` | 连接配置 | ✅ 使用中 | - |
| `browser` | 浏览器配置 | ✅ 使用中 | BrowserConfig |
| `crawler` | 爬虫配置 | ✅ 使用中 | CrawlerRunConfig |
| `http` | HTTP配置 | 🔄 预留 | HTTPCrawlerConfig |
| `geolocation` | 地理位置 | 🔄 预留 | GeolocationConfig |
| `proxy` | 代理配置 | 🔄 预留 | ProxyConfig |
| `virtual_scroll` | 虚拟滚动 | 🔄 预留 | VirtualScrollConfig |
| `link_preview` | 链接预览 | 🔄 预留 | LinkPreviewConfig |
| `llm` | LLM配置 | 🔄 预留 | LLMConfig |
| `seeding` | 种子配置 | 🔄 预留 | SeedingConfig |

## 📊 参数速查表

### Default 配置

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `base_url` | string | Docker服务地址 | `http://localhost:11235` |
| `timeout` | int | 请求超时(秒) | `60` |
| `stream_timeout` | int | 流式请求超时(秒) | `120` |
| `retry_attempts` | int | 重试次数 | `2` |
| `token` | string | 认证令牌 | `null` |

### Browser Config (浏览器配置)

#### 基础参数

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `browser_type` | string | 浏览器类型 | `chromium` |
| `headless` | bool | 无头模式 | `true` |
| `viewport_width` | int | 视口宽度 | `1080` |
| `viewport_height` | int | 视口高度 | `600` |
| `user_agent` | string | 用户代理 | Chrome UA |
| `ignore_https_errors` | bool | 忽略HTTPS错误 | `true` |
| `java_script_enabled` | bool | 启用JavaScript | `true` |

#### 高级参数

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `enable_stealth` | bool | 反检测模式 | `false` |
| `browser_mode` | string | 浏览器模式 | `dedicated` |
| `proxy` | string | 代理服务器 | `null` |
| `text_mode` | bool | 文本模式(禁用图片) | `false` |
| `light_mode` | bool | 轻量模式 | `false` |
| `extra_args` | list | 额外启动参数 | `[]` |

### Crawler Config (爬虫配置)

#### 内容处理

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `word_count_threshold` | int | 最小字数 | `200` |
| `only_text` | bool | 仅文本 | `false` |
| `excluded_tags` | list | 排除标签 | `["nav","footer"...]` |
| `css_selector` | string | CSS选择器 | `null` |
| `target_elements` | list | 目标元素 | `[]` |
| `excluded_selector` | string | 排除选择器 | `""` |

#### 页面加载

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `wait_until` | string | 等待条件 | `domcontentloaded` |
| `page_timeout` | int | 超时(毫秒) | `60000` |
| `wait_for` | string | 等待元素 | `null` |
| `delay_before_return_html` | float | 返回前延迟(秒) | `0.1` |

#### 交互行为

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `scan_full_page` | bool | 滚动整页 | `false` |
| `scroll_delay` | float | 滚动延迟(秒) | `0.2` |
| `max_scroll_steps` | int | 最大滚动次数 | `null` |
| `simulate_user` | bool | 模拟用户 | `false` |
| `remove_overlay_elements` | bool | 移除遮罩 | `false` |
| `magic` | bool | 自动处理弹窗 | `false` |
| `js_code` | string/list | JavaScript代码 | `null` |

#### 媒体处理

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `screenshot` | bool | 截图(base64) | `false` |
| `pdf` | bool | 生成PDF(base64) | `false` |
| `exclude_external_images` | bool | 排除外部图片 | `false` |
| `exclude_all_images` | bool | 排除所有图片 | `false` |

#### LLM 优化参数 ⭐

| 参数 | 类型 | 说明 | 推荐值 |
|------|------|------|--------|
| `return_format` | string | 返回格式 | `markdown` |
| `content_filter_type` | string | 过滤类型 | `pruning` / `bm25` |
| `pruning_threshold` | float | 修剪阈值 | `0.48` |
| `pruning_threshold_type` | string | 阈值类型 | `fixed` |
| `min_word_threshold` | int | 最小词数 | `30` |
| `bm25_threshold` | float | BM25阈值 | `1.0` |
| `user_query` | string | 查询关键词 | 相关词 |
| `max_token_length` | int | 最大token | 根据需要 |
| `prefer_fit_markdown` | bool | 优先fit | `true` |
| `extract_main_content` | bool | 主要内容 | `true` |

#### 链接控制

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `exclude_external_links` | bool | 排除外链 | `false` |
| `exclude_internal_links` | bool | 排除内链 | `false` |
| `exclude_social_media_links` | bool | 排除社交媒体 | `false` |
| `exclude_domains` | list | 排除域名 | `[]` |

#### 缓存和性能

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `cache_mode` | string | 缓存模式 | `bypass` |
| `semaphore_count` | int | 并发限制 | `5` |
| `verbose` | bool | 详细日志 | `true` |

## 特定使用场景配置示例

### 1. 基础网页爬取
```json
{
  "default": {
    "base_url": "http://localhost:11235",
    "timeout": 60
  },
  "browser": {
    "headless": true,
    "viewport_width": 1280,
    "viewport_height": 720
  },
  "crawler": {
    "word_count_threshold": 100,
    "cache_mode": "bypass",
    "verbose": true,
    "return_format": "markdown"
  }
}
```

### 2. 新闻内容提取
```json
{
  "default": {
    "base_url": "http://localhost:11235",
    "timeout": 60
  },
  "browser": {
    "headless": true
  },
  "crawler": {
    "word_count_threshold": 300,
    "only_text": true,
    "excluded_tags": ["nav", "footer", "aside", "script", "style", "header", "advertisement"],
    "css_selector": "article",
    "exclude_external_images": true,
    "verbose": false,
    "prefer_fit_markdown": true,
    "content_filter_type": "pruning",
    "pruning_threshold": 0.5
  }
}
```

### 3. 电商产品信息提取
```json
{
  "default": {
    "base_url": "http://localhost:11235",
    "timeout": 120
  },
  "browser": {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "viewport_width": 1920,
    "viewport_height": 1080,
    "simulate_user": true
  },
  "crawler": {
    "word_count_threshold": 50,
    "only_text": false,
    "target_elements": [".product-price", ".product-title", ".product-description", ".product-image"],
    "cache_mode": "bypass",
    "wait_until": "networkidle",
    "scan_full_page": true,
    "scroll_delay": 0.5,
    "remove_overlay_elements": true,
    "verbose": true,
    "prefer_fit_markdown": true,
    "exclude_external_links": false
  }
}
```

### 4. 反爬虫网站处理
```json
{
  "default": {
    "base_url": "http://localhost:11235",
    "timeout": 180
  },
  "browser": {
    "user_agent_mode": "random",
    "enable_stealth": true,
    "ignore_https_errors": true,
    "headless": true
  },
  "crawler": {
    "word_count_threshold": 100,
    "simulate_user": true,
    "wait_for_images": true,
    "delay_before_return_html": 2.0,
    "mean_delay": 1.0,
    "max_range": 2.0,
    "cache_mode": "bypass",
    "wait_until": "networkidle",
    "remove_overlay_elements": true,
    "magic": true,
    "js_code": ["window.scrollTo(0, document.body.scrollHeight);", "await new Promise(r => setTimeout(r, 2000));"],
    "verbose": true
  }
}
```

### 5. PDF报告生成
```json
{
  "default": {
    "base_url": "http://localhost:11235",
    "timeout": 90
  },
  "browser": {
    "viewport_width": 1200,
    "viewport_height": 1600
  },
  "crawler": {
    "word_count_threshold": 100,
    "pdf": true,
    "screenshot": false,
    "prettiify": true,
    "parser_type": "lxml",
    "verbose": false,
    "prefer_fit_markdown": true
  }
}
```

### 6. 社交媒体内容爬取
```json
{
  "default": {
    "base_url": "http://localhost:11235",
    "timeout": 180
  },
  "browser": {
    "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X)",
    "viewport_width": 375,
    "viewport_height": 667,
    "simulate_user": true
  },
  "crawler": {
    "word_count_threshold": 10,
    "scan_full_page": true,
    "max_scroll_steps": 20,
    "scroll_delay": 1.0,
    "wait_until": "networkidle",
    "remove_overlay_elements": true,
    "magic": true,
    "exclude_external_links": false,
    "exclude_internal_links": false,
    "verbose": true,
    "prefer_fit_markdown": true,
    "content_filter_type": "pruning",
    "pruning_threshold": 0.3
  }
}
```

## 获取 fit_markdown 和控制链接的参数配置

### 控制 Markdown 类型的参数：
- `prefer_fit_markdown`: 设置为 `true` 优先返回 fit_markdown
- `content_filter_type`: 设置为 `"pruning"` 使用内容修剪算法生成 fit_markdown
- `pruning_threshold`: 控制内容修剪的阈值，值越高保留的内容越少（建议 0.3-0.7）

### 控制链接保留的参数：
- `exclude_external_links`: 
  - `false`: 保留外部链接（默认）
  - `true`: 移除外部链接
- `exclude_internal_links`:
  - `false`: 保留内部链接（默认）
  - `true`: 移除内部链接
- `exclude_social_media_links`:
  - `false`: 保留社交媒体链接（默认）
  - `true`: 移除社交媒体链接
- `only_text`: 如果设置为 `true` 会移除链接等富媒体内容

### 获取 fit_markdown 并保留链接的配置示例：
```json
{
  "crawler": {
    "prefer_fit_markdown": true,
    "content_filter_type": "pruning",
    "pruning_threshold": 0.5,
    "min_word_threshold": 30,
    "exclude_external_links": false,
    "exclude_internal_links": false,
    "exclude_social_media_links": false,
    "only_text": false
  }
}
```

## 🚀 快速开始

### 1. 创建配置文件

```bash
# 使用简化模板(推荐)
cp config.template.json config.json

# 或使用完整示例
cp config_example.json config.json
```

### 2. 编辑配置

```json
{
  "default": {
    "base_url": "http://localhost:11235"
  },
  "browser": {
    "viewport_width": 1920,
    "enable_stealth": false
  },
  "crawler": {
    "word_count_threshold": 200,
    "prefer_fit_markdown": true,
    "verbose": true
  }
}
```

### 3. 使用配置

**Agent 自动调用(推荐):**
```
User: 请帮我爬取 https://example.com 的内容
```

**程序化调用:**
```python
from src.tools.connector.crawl4ai import get_tools

tools = get_tools()
crawl_tool = tools[0]

# 使用配置文件参数
result = await crawl_tool._arun(urls=["https://example.com"])

# 覆盖部分参数
result = await crawl_tool._arun(
    urls=["https://example.com"],
    crawler_config={"verbose": False}
)
```

## ✅ 配置验证

### 检查服务状态

```bash
# 使用 CLI 命令
:connector status

# 或使用 curl
curl http://localhost:11235/health
```

### 验证配置加载

```python
from src.tools.connector.crawl4ai.config import Crawl4AIConfig

config = Crawl4AIConfig()
print(f"Base URL: {config.base_url}")
print(f"Browser Config: {config.browser_config}")
print(f"Crawler Config: {config.crawler_config}")
```

### 常见问题

**问题: 配置参数不生效**
- ✅ 检查 config.json 是否存在
- ✅ 检查 JSON 语法是否正确
- ✅ 确认参数名称拼写正确
- ✅ 查看日志确认参数传递

**问题: Docker 服务连接失败**
- ✅ 检查 Docker 容器是否运行: `docker ps`
- ✅ 确认端口映射: `11235:11235`
- ✅ 测试连接: `curl http://localhost:11235/health`

## 📚 相关文档

- **[crawl4ai_guide.md](../../../tutorials/connector/crawl4ai/crawl4ai_guide.md)** - 完整使用教程
- **[crawl4ai_fix.md](../../../tutorials/connector/crawl4ai/crawl4ai_fix.md)** - 参数传递流程和技术细节
- **[config_example.json](./config_example.json)** - 完整配置示例
- **[config.template.json](./config.template.json)** - 简化配置模板
- **[config.json.commented](./config.json.commented)** - 带注释的配置说明