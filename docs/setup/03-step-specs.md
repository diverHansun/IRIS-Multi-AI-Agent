# 各 Setup Step 详细规格

## 1. 概述

本文档定义 Setup Wizard 中四个配置步骤的详细行为规格，
包含交互流程、数据读写、校验逻辑和边界条件处理。

## 2. 公共基类

### 2.1 SetupStep

```python
class SetupStep(ABC):
    """Abstract base class for all setup steps."""

    name: str           # step identifier, e.g., "llm", "agent", "tools", "dify"
    title: str          # display title, e.g., "LLM Provider Configuration"
    skippable: bool     # whether this step can be skipped

    @abstractmethod
    def run(self, context: SetupContext, sub_target: str = None) -> StepResult:
        """Execute the configuration step interactively."""

    @abstractmethod
    def check(self, context: SetupContext) -> List[CheckResult]:
        """Health check for this step (used by iris doctor)."""
```

### 2.2 StepResult

```python
@dataclass
class StepResult:
    """Result of a setup step execution."""

    success: bool = False
    skipped: bool = False
    error: str = ""
    configured_items: List[str] = field(default_factory=list)
```

### 2.3 CheckResult

```python
@dataclass
class CheckResult:
    """Result of a single health check item."""

    name: str           # e.g., "ZHIPU_API_KEY"
    status: str         # "pass", "fail", "warn"
    message: str        # human-readable description
    category: str       # "llm", "agent", "tools", "dify"
```

## 3. Step 1: LLMSetupStep

### 3.1 基本信息

| 属性 | 值 |
|------|-----|
| name | `"llm"` |
| title | `"LLM Provider Configuration"` |
| skippable | `False` -- at least one LLM API key is required |

### 3.2 支持的 Provider 列表

| Provider | API Key Env | Default Model | Description |
|----------|-------------|---------------|-------------|
| zhipu | `ZHIPU_API_KEY` | `glm-4.5-flash` | Zhipu GLM (recommended, free tier available) |
| openai | `OPENAI_API_KEY` | `gpt-4o-mini` | OpenAI GPT (supports custom base_url) |
| tongyi | `TONGYI_API_KEY` | `qwen3-max` | Tongyi Qwen |
| ollama | (none) | `auto` | Local models (no API key needed) |

### 3.3 交互流程

```
Step 1/4: LLM Provider Configuration
======================================

Supported providers:
+----------+------------------------------------------+-----------------+
| Provider | Description                              | Status          |
+----------+------------------------------------------+-----------------+
| zhipu    | Zhipu GLM (recommended, free tier)       | not configured  |
| openai   | OpenAI GPT (supports custom base_url)    | not configured  |
| tongyi   | Tongyi Qwen                              | not configured  |
| ollama   | Local models (no API key needed)          | available       |
+----------+------------------------------------------+-----------------+

[PgUp/PgDn] Navigate  [Enter] Select

> Select default provider: zhipu

  ZHIPU_API_KEY: ****************************
  [*] API key saved

  Configure another provider? (y/N): y

  > Select provider: openai
  OPENAI_API_KEY: ****************************
  Custom base URL (press Enter to skip): https://my-proxy.com/v1
  [*] API key and base URL saved

  Configure another provider? (y/N): N
```

### 3.4 处理逻辑

1. 读取 `~/.iris/.env`，检测各 provider 的 API key 状态
2. 使用 `SelectOne` 控件让用户选择默认 provider
3. 如果选的不是 ollama，使用 `Prompt.ask()` 输入 API key
4. 如果选 openai，额外询问 `OPENAI_BASE_URL`
5. 通过 `EnvWriter` 写入：
   - `{PROVIDER}_API_KEY=xxx`
   - `DEFAULT_LLM_PROVIDER=zhipu`
   - `DEFAULT_LLM_MODEL=glm-4.5-flash`
   - `OPENAI_BASE_URL=xxx`（如有）
6. 循环询问"是否配置其他 provider"
7. 更新 `context.configured_providers`

### 3.5 校验规则

- API key 不能为空
- API key 不能是占位符（以 `your_` 开头）
- 至少配置一个 provider（ollama 单独也算通过）

### 3.6 check() 行为（doctor 用）

```
[pass] ZHIPU_API_KEY is configured
[fail] OPENAI_API_KEY is not configured
[pass] DEFAULT_LLM_PROVIDER = zhipu (API key available)
```

## 4. Step 2: AgentSetupStep

### 4.1 基本信息

| 属性 | 值 |
|------|-----|
| name | `"agent"` |
| title | `"Agent Configuration"` |
| skippable | `True` |

### 4.2 子步骤：Basic Mode

纯确认性展示，无需用户输入：

```
Agent Configuration - Basic Mode
==================================
Basic agent will use: zhipu / glm-4.5-flash
  (derived from LLM configuration)
```

逻辑：
- 读取 `context.configured_providers` 中的默认 provider
- 映射到 basic agent 的默认 model
- 展示确认信息

### 4.3 子步骤：Deep Mode

```
Agent Configuration - Deep Mode
==================================
Configure deep agent mode? (y/N): y

Main agent providers (mainagents.json):
+-----------+--------------------+-----------------+
| Provider  | Model              | API Key Status  |
+-----------+--------------------+-----------------+
| zhipu     | glm-4.6            | configured      |
| tongyi    | qwen3-max          | not configured  |
| openai    | gpt-4o             | not configured  |
+-----------+--------------------+-----------------+

Deep mode will use first provider with a configured API key.
Current selection: zhipu / glm-4.6

Sub-agents (subagents.json):
+-----------+-----------+--------------------+-----------------+
| Role      | Provider  | Model              | Status          |
+-----------+-----------+--------------------+-----------------+
| research  | zhipu     | glm-4.5-flash      | configured      |
| coding    | tongyi    | qwen3-coder-plus   | not configured  |
| analysis  | zhipu     | glm-4.5-flash      | configured      |
+-----------+-----------+--------------------+-----------------+

[!] Sub-agent "coding" requires TONGYI_API_KEY (not configured).
    It will fall back to: zhipu / glm-4.5-flash

Configure missing API keys? (y/N):
```

逻辑：
1. 询问用户是否配置 deep 模式
2. 读取 `~/.iris/agents/deep/mainagents.json`，列出各 provider 及 key 状态
3. 读取 `~/.iris/agents/deep/subagents.json`，列出各 subagent 的 provider 及 key 状态
4. 对缺失 key 的 subagent 提示 fallback 策略
5. 可选输入缺失的 API key

### 4.4 子步骤参数映射

| 参数 | 行为 |
|------|------|
| `sub_target=None` | 运行 basic + deep 两个子步骤 |
| `sub_target="basic"` | 仅运行 basic 子步骤 |
| `sub_target="deep"` | 仅运行 deep 子步骤 |

### 4.5 check() 行为（doctor 用）

```
[pass] Basic agent: zhipu / glm-4.5-flash (API key available)
[warn] Deep main agent: tongyi provider not configured (fallback to zhipu)
[warn] Deep sub-agent "coding": TONGYI_API_KEY missing (fallback to zhipu)
[pass] Deep sub-agent "research": zhipu configured
[pass] Deep sub-agent "analysis": zhipu configured
```

## 5. Step 3: ToolsSetupStep

### 5.1 基本信息

| 属性 | 值 |
|------|-----|
| name | `"tools"` |
| title | `"Tools Configuration"` |
| skippable | `True` -- every tool can be skipped individually |

### 5.2 SDK 工具列表

| Tool | Required Key | Description | Notes |
|------|-------------|-------------|-------|
| Tavily Search | `TAVILY_API_KEY` | Web search API | optional |
| DuckDuckGo | (none) | Free web search | always available |
| Zhipu Search | `ZHIPU_API_KEY` | Zhipu search integration | reuses LLM key |
| Zhipu Crawl | `ZHIPU_API_KEY` | Zhipu content crawling | reuses LLM key |
| AMap Services | `AMAP_API_KEY` | Map search and routing | optional |

### 5.3 MCP 工具列表

基于当前 `~/.iris/tools/mcp/mcp.toml` 实际配置：

| Server | Required Key | Description |
|--------|-------------|-------------|
| Notion | `NOTION_TOKEN` | Notion page/database integration |
| Context7 | `CONTEXT7_API_KEY` | Context7 MCP service |
| AMap Maps | `AMAP_MAPS_API_KEY` | AMap maps MCP service |
| Firecrawl | `FIRECRAWL_API_KEY` | Web crawling via Firecrawl |
| Chrome DevTools | (none) | Browser automation |

注意：MCP Filesystem 不在配置范围内，已去除。

### 5.4 交互流程

```
Step 3/4: Tools Configuration
===============================

--- SDK Tools ---
+---------------+------------------+-----------------+
| Tool          | Required Key     | Status          |
+---------------+------------------+-----------------+
| Tavily Search | TAVILY_API_KEY   | not configured  |
| DuckDuckGo    | (no key needed)  | available       |
| Zhipu Search  | ZHIPU_API_KEY    | configured      |
| Zhipu Crawl   | ZHIPU_API_KEY    | configured      |
| AMap Services | AMAP_API_KEY     | not configured  |
+---------------+------------------+-----------------+

Configure TAVILY_API_KEY? (y/skip): skip
Configure AMAP_API_KEY? (y/skip): skip

--- MCP Tools ---
+-----------------+--------------------+-----------------+
| Server          | Required Key       | Status          |
+-----------------+--------------------+-----------------+
| Notion          | NOTION_TOKEN       | not configured  |
| Context7        | CONTEXT7_API_KEY   | not configured  |
| AMap Maps       | AMAP_MAPS_API_KEY  | not configured  |
| Firecrawl       | FIRECRAWL_API_KEY  | not configured  |
| Chrome DevTools | (no key needed)    | available       |
+-----------------+--------------------+-----------------+

Configure NOTION_TOKEN? (y/skip): skip
Configure CONTEXT7_API_KEY? (y/skip): skip
Configure AMAP_MAPS_API_KEY? (y/skip): skip
Configure FIRECRAWL_API_KEY? (y/skip): skip
```

### 5.5 处理逻辑

1. 列出所有 SDK 工具及其 key 状态
2. 对已通过 LLM step 配置的 key（如 ZHIPU_API_KEY）自动标注 `configured`
3. 逐个询问未配置的 SDK 工具 key
4. 列出所有 MCP 工具及其 key 状态
5. 逐个询问未配置的 MCP 工具 key
6. 无 key 工具（DuckDuckGo、Chrome DevTools）直接标注 `available`

### 5.6 子步骤参数映射

| 参数 | 行为 |
|------|------|
| `sub_target=None` | 运行 SDK + MCP 两组 |
| `sub_target="sdk"` | 仅运行 SDK 工具配置 |
| `sub_target="mcp"` | 仅运行 MCP 工具配置 |

### 5.7 check() 行为（doctor 用）

```
[pass] DuckDuckGo: available (no key needed)
[pass] Zhipu Search: ZHIPU_API_KEY configured
[warn] Tavily Search: TAVILY_API_KEY not configured (search fallback to DuckDuckGo)
[warn] Notion MCP: NOTION_TOKEN not configured
[pass] Chrome DevTools MCP: available (no key needed)
```

## 6. Step 4: DifySetupStep

### 6.1 基本信息

| 属性 | 值 |
|------|-----|
| name | `"dify"` |
| title | `"Dify Engine Configuration"` |
| skippable | `True` |

### 6.2 交互流程

```
Step 4/4: Dify Engine Configuration
=====================================
Dify engine requires an API key from your Dify instance.

Configure Dify? (y/skip): y
  DIFY_API_KEY: ****************************
  DIFY_BASE_URL [https://api.dify.ai/v1]:
  [*] Dify configuration saved
```

### 6.3 处理逻辑

1. 询问是否配置 Dify
2. 输入 `DIFY_API_KEY`
3. 输入 `DIFY_BASE_URL`，提供默认值 `https://api.dify.ai/v1`
4. 写入 `.env`

### 6.4 check() 行为（doctor 用）

```
[pass] DIFY_API_KEY is configured
[pass] DIFY_BASE_URL = https://api.dify.ai/v1
```
或：
```
[warn] DIFY_API_KEY not configured (Dify engine unavailable, can be skipped)
```

## 7. 完整 check() 输出示例（iris doctor）

```
IRIS Configuration Health Check
=================================

LLM:
  [pass] ZHIPU_API_KEY configured
  [pass] OPENAI_API_KEY configured
  [fail] TONGYI_API_KEY not configured
  [pass] DEFAULT_LLM_PROVIDER = zhipu (key available)

Agent - Basic:
  [pass] Basic agent: zhipu / glm-4.5-flash (key available)

Agent - Deep:
  [pass] Main agent: zhipu / glm-4.6 (key available)
  [warn] Main agent: tongyi not configured (fallback available)
  [pass] Sub-agent "research": zhipu configured
  [warn] Sub-agent "coding": tongyi not configured (fallback to zhipu)
  [pass] Sub-agent "analysis": zhipu configured

Tools - SDK:
  [pass] DuckDuckGo: available
  [pass] Zhipu Search: configured
  [warn] Tavily Search: not configured
  [warn] AMap Services: not configured

Tools - MCP:
  [warn] Notion: NOTION_TOKEN not configured
  [warn] Context7: not configured
  [warn] AMap Maps: not configured
  [warn] Firecrawl: not configured
  [pass] Chrome DevTools: available

Dify:
  [warn] DIFY_API_KEY not configured

Summary: 8 passed, 1 failed, 7 warnings
```
