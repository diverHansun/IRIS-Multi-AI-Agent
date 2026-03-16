# IRIS:Muti-AI-Agent – Setup Guide

This guide covers installation, the interactive setup wizard, and configuration management for the `iris` command.

---

## 1. Prerequisites

- Windows + PowerShell
- Python 3.10+
- `uv` installed (`pip install uv` or download from the uv site)
- Project virtualenv ready at `.venv` (run `uv sync` in the project root first)

---

## 2. Build & Install

Run in the project root:

```powershell
.venv\Scripts\activate
uv tool uninstall iris-muti-ai-agent 2>$null
uv tool install --python .venv\Scripts\python.exe --editable --force --reinstall --refresh --no-cache .
```

- Brand label: `IRIS:muti-ai-agent`
- Package id: `iris-muti-ai-agent` (used by `uv tool`)

This installs `iris` to your user tool path (e.g. `C:\Users\<you>\.local\bin\iris.exe`).

### Rebuild after code changes

```powershell
uv tool install --python .venv\Scripts\python.exe --editable --force --reinstall --refresh --no-cache .
```

---

## 3. First Launch & Global Config

```powershell
iris
```

On first run, IRIS creates `~/.iris/` and copies bundled default configs:

```
C:\Users\<you>\.iris\
├── config.toml          # main config (LLM, agent, tools settings)
├── .env                 # API keys (created from template)
├── agents/
│   ├── basic/           # basic agent provider config
│   └── deep/            # deep agent config (mainagents.json, subagents.json)
└── tools/
    └── mcp/
        └── mcp.toml     # MCP server config
```

To reset the global config:

```powershell
Remove-Item -Recurse -Force $env:USERPROFILE\.iris
iris
```

---

## 4. Setup Wizard

### 4.1 First-Time Auto-Trigger

On first launch, if `setup.completed = false` in `config.toml`, IRIS automatically starts the setup wizard. This guides you through four configuration steps.

### 4.2 Run the Wizard Manually

```
/setup
```

Runs all four steps in sequence:
1. LLM Provider Configuration
2. Agent Configuration
3. Tools Configuration
4. Dify Engine Configuration

### 4.3 Run a Specific Step

```
/setup --llm          # LLM providers only
/setup --agent        # agent config only (basic + deep)
/setup --agent basic  # basic agent only
/setup --agent deep   # deep agent only
/setup --tools        # tools only (SDK + MCP)
/setup --tools sdk    # SDK tools only
/setup --tools mcp    # MCP tools only
/setup --dify         # Dify engine only
```

### 4.4 Interactive UX

**Navigation controls:**
- `Up / Down` — move cursor in selection lists
- `Enter` — confirm selection or input
- `Esc` — cancel / go back to previous selector

**Text inputs:**
- API keys are shown in plaintext (no masking) during typing
- Existing values are pre-filled as the default — press `Enter` to confirm without retyping
- Press `Esc` during input to cancel and return to the previous screen

**Selection lists (SelectOne):**
- `[Up/Down]` Navigate
- `[Enter]` Select
- `[Esc]` Cancel

**Multi-select lists (SelectMany):**
- `[Up/Down]` Navigate
- `[Space]` Toggle
- `[Enter]` Confirm
- `[a]` Select all
- `[n]` Select none
- `[Esc]` Cancel

---

## 5. Configuration Steps

### Step 1: LLM Provider Configuration (required)

At least one LLM provider must be configured. Supported providers:

| Provider | API Key Env | Default Model | Notes |
|----------|-------------|---------------|-------|
| zhipu | `ZHIPU_API_KEY` | `glm-4.5-flash` | Recommended, free tier available |
| openai | `OPENAI_API_KEY` | `gpt-4o-mini` | Supports custom `OPENAI_BASE_URL` |
| tongyi | `TONGYI_API_KEY` | `qwen3-max` | Alibaba Cloud Dashscope |
| ollama | (none) | `auto` | Local models, no key needed |

For OpenAI, the wizard prompts for `OPENAI_BASE_URL` first (default: `https://api.openai.com/v1`), then the API key. This allows configuring compatible proxy endpoints.

Written to `~/.iris/.env`:
- `{PROVIDER}_API_KEY`
- `DEFAULT_LLM_PROVIDER`
- `DEFAULT_LLM_MODEL`
- `OPENAI_BASE_URL` (if OpenAI selected)

### Step 2: Agent Configuration (skippable)

**Basic mode** — no additional keys needed. Uses the LLM provider configured in Step 1.

**Deep mode** — reads `~/.iris/agents/deep/mainagents.json` and `subagents.json`, shows each provider's key status, and optionally prompts for missing API keys. Sub-agents without a configured key fall back to the first available provider.

API keys are shared between basic and deep modes — configuring a provider in Step 1 makes it available for all agent modes automatically.

### Step 3: Tools Configuration (skippable)

**SDK Tools:**

| Tool | Required Key | Notes |
|------|-------------|-------|
| Tavily Search | `TAVILY_API_KEY` | Optional web search |
| DuckDuckGo | (none) | Always available |
| Zhipu Search | `ZHIPU_API_KEY` | Reuses LLM key |
| Zhipu Crawl | `ZHIPU_API_KEY` | Reuses LLM key |
| AMap Services | `AMAP_API_KEY` | Map search/routing |

**MCP Tools:**

| Server | Required Key | Description |
|--------|-------------|-------------|
| Notion | `NOTION_TOKEN` | Notion page/database |
| Context7 | `CONTEXT7_API_KEY` | Context7 MCP service |
| AMap Maps | `AMAP_MAPS_API_KEY` | AMap maps MCP |
| Firecrawl | `FIRECRAWL_API_KEY` | Web crawling |
| Chrome DevTools | (none) | Browser automation |

Each tool is presented individually — you can skip any. Already-configured keys are pre-filled. `ZHIPU_API_KEY` is prompted only once even though it is shared by Zhipu Search and Zhipu Crawl.

MCP tool keys are written to `~/.iris/.env` and automatically passed to MCP server processes via environment variable expansion (`$VAR` syntax in `mcp.toml`).

### Step 4: Dify Engine Configuration (skippable)

Optional. Required only if you use the Dify engine.

| Variable | Default |
|----------|---------|
| `DIFY_API_KEY` | (required) |
| `DIFY_BASE_URL` | `https://api.dify.ai/v1` |

---

## 6. Doctor Check

```
/doctor
```

Runs health checks across all configuration areas and prints a status report:

```
IRIS Configuration Health Check
=================================

LLM:
  [pass] ZHIPU_API_KEY configured
  [warn] OPENAI_API_KEY not configured
  [pass] DEFAULT_LLM_PROVIDER = zhipu (key available)

Agent - Basic:
  [pass] Basic agent: zhipu / glm-4.5-flash (key available)

Agent - Deep:
  [pass] Main agent: zhipu / glm-4.6 (key available)
  [warn] Sub-agent "coding": TONGYI_API_KEY missing (fallback to zhipu)

Tools - SDK:
  [pass] DuckDuckGo: available
  [pass] Zhipu Search: configured
  [warn] Tavily Search: TAVILY_API_KEY not configured

Tools - MCP:
  [warn] Notion: NOTION_TOKEN not configured
  [pass] Chrome DevTools: available (no key needed)

Dify:
  [warn] DIFY_API_KEY not configured

Summary: N passed, N failed, N warnings
```

`/doctor` reads configuration from `~/.iris/.env` (loaded automatically at startup into `os.environ`).

---

## 7. API Key Storage

All API keys are stored in `~/.iris/.env`. The setup wizard writes keys here via `EnvWriter`, which also sets them in `os.environ` immediately so the running process can use them without restart.

The `.env` file is loaded automatically at startup by `env_loader.py`.

**Manual editing** is also supported:

```powershell
notepad $env:USERPROFILE\.iris\.env
```

Key format follows standard dotenv syntax:

```env
ZHIPU_API_KEY=your_actual_key_here
DEFAULT_LLM_PROVIDER=zhipu
DEFAULT_LLM_MODEL=glm-4.5-flash
```

Placeholder values starting with `your_` are treated as unconfigured by the wizard and doctor.

---

## 8. Config Precedence (highest wins)

1. Current directory `.env`
2. Current project `.iris/` (if present)
3. Global `C:\Users\<you>\.iris\.env`
4. Bundled defaults inside the installed package

If `iris` reports missing configs or keys, ensure the relevant key exists in one of the higher-priority locations above.

---

## 9. MCP Tool Configuration

MCP servers are configured in `~/.iris/tools/mcp/mcp.toml`. Each server's env block uses `$VAR` syntax — IRIS expands these from `os.environ` at runtime:

```toml
[mcp_servers.notion]
transport = "stdio"
command = "npx"
args = ["-y", "@notionhq/notion-mcp-server"]
rename_prefix = "notion:"

[mcp_servers.notion.env]
NOTION_TOKEN = "$NOTION_TOKEN"
```

To activate a MCP server:
1. Configure its API key via `/setup --tools mcp` or add it to `~/.iris/.env` manually
2. Ensure the server entry exists in `~/.iris/tools/mcp/mcp.toml`
3. Restart IRIS (or run `/setup` again to reload)

---

## 10. Verify Installation

```powershell
where iris                     # should show ...\.local\bin\iris.exe
dir $env:USERPROFILE\.iris     # should contain config.toml, .env, agents/, tools/
```

Run `/doctor` inside IRIS to verify all configured keys are detected correctly.
