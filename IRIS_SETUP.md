# IRIS:Muti-AI-Agent – Setup Guide

This guide covers installation, the interactive setup wizard, and configuration management for the `iris` command.

---

## 1. Prerequisites

- macOS (zsh/bash), Linux (bash), or Windows (PowerShell)
- Python 3.10+
- `uv` installed (`pip install uv` or download from the uv site)
- Project virtualenv ready at `.venv` (run `uv sync` in the project root first)

---

## 2. Build & Install

### macOS: project virtual environment

Run from this checkout:

```bash
./scripts/setup-macos.sh
uv run --locked iris
```

The script uses Python 3.11, installs the locked dependencies into `.venv`, initializes `~/.iris/`, and creates `.env` with empty API keys and mode `600` only if absent. Existing configuration is preserved. If `uv` is missing, install it with `brew install uv`.

For manual installation:

```bash
uv sync --python 3.11 --locked
source .venv/bin/activate
iris
```

Use the first-launch wizard to configure a provider, or edit `~/.iris/.env`. For OpenAI-compatible services, configure `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `DEFAULT_LLM_PROVIDER=openai`, and `DEFAULT_LLM_MODEL`. Do not mark setup complete until the provider is configured. `python main.py` uses the same startup wizard as `iris` and also accepts `--debug`.

To update this checkout, run `uv sync --python 3.11 --locked` again. Editable installation makes source changes immediately available. A separate `uv tool install` is optional and creates another environment.

Shell middleware defaults to `shell_type: "auto"` (Windows: cmd; macOS/Linux: bash). If importing an old Windows shell config, set `~/.iris/agents/deep/middleware/shell.json` to `auto`. The interactive terminal can remain zsh.

Node.js/`npx` is needed for stdio MCP servers. The Crawl4AI connector talks to a separate service at `http://localhost:11235`; it is not started by the installer. Docker and Ollama are optional and must be configured separately if used.

### Windows: project virtual environment

Run in PowerShell from the project root:

```powershell
uv sync --python 3.11 --locked
uv run --locked iris
```

Optional activation:

```powershell
.\.venv\Scripts\Activate.ps1
iris
```

If PowerShell blocks the activation script, use `uv run --locked iris` directly. It does not require activating the environment manually. The first-launch wizard initializes `$env:USERPROFILE\.iris`.

### Platform reference

| Item | Windows | macOS |
| --- | --- | --- |
| Python executable | `.venv\Scripts\python.exe` | `.venv/bin/python` |
| Activate environment | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| User configuration | `%USERPROFILE%\.iris` | `~/.iris` |
| Persistent agent Shell with `auto` | `cmd.exe /Q` | `/bin/bash --norc --noprofile` |
| Project launch | `uv run --locked iris` | `uv run --locked iris` |

The terminal used to launch IRIS and the agent's persistent Shell are separate: launching from PowerShell does not change the default agent Shell to PowerShell, and launching from zsh does not change it to zsh. An explicit `powershell` branch exists on Windows, but it is outside this round's live validation; use `auto` for the cross-platform baseline.

**Validation as of 2026-10-06:** macOS Apple Silicon installation and live BasicAgent/DeepAgent conversations passed. Windows Shell command selection was checked, but a full Windows-machine run remains pending. Linux shares the POSIX branch and was not validated on a Linux machine in this round.

When moving between systems, rebuild `.venv`; do not copy it. Update absolute workspace/file paths and OS-specific `startup_commands`. Config-relative references accept either separator, but a Windows drive path such as `C:\...` does not map to a macOS file automatically. Existing user configs are preserved, so replace an old `shell_type: "cmd"` with `auto` when migrating.

### Windows: optional user tool installation

Run in the project root:

```powershell
.\.venv\Scripts\Activate.ps1
uv tool uninstall iris-muti-ai-agent 2>$null
uv tool install --python .venv\Scripts\python.exe --editable --force --reinstall --refresh --no-cache .
```

- Brand label: `IRIS:muti-ai-agent`
- Package id: `iris-muti-ai-agent` (used by `uv tool`)

This installs `iris` to your user tool path (e.g. `C:\Users\<you>\.local\bin\iris.exe`).

### Update after changes

Source edits are picked up by editable installations. To synchronize project dependencies on either Windows or macOS:

```text
uv sync --python 3.11 --locked
```

For a separate Windows user tool environment:

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
~/.iris/                     # Windows: C:\Users\<you>\.iris\
├── config.toml          # main config (LLM, agent, tools settings)
├── .env                 # API keys (created from template)
├── agents/
│   ├── basic/           # basic agent provider config
│   └── deep/            # deep agent config (mainagents.json, subagents.json)
└── tools/
    └── mcp/
        └── mcp.toml     # MCP server config
```

To reset the global config on Windows (this removes saved keys and settings):

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

```bash
# macOS / Linux
nano ~/.iris/.env
```

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
3. Global `~/.iris/.env` (Windows: `C:\Users\<you>\.iris\.env`)
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

```bash
# macOS / Linux, from the project directory
uv pip check
.venv/bin/python -c 'import platform, sys; print(platform.machine(), sys.prefix)'
ls ~/.iris
uv run --locked iris
# Then run /doctor in the CLI.
```


```powershell
# Windows PowerShell, from the project directory
uv pip check
.\.venv\Scripts\python.exe -c "import platform, sys; print(platform.machine(), sys.prefix)"
Get-ChildItem $env:USERPROFILE\.iris
uv run --locked iris
# After activation or uv tool installation, locate the executable with:
Get-Command iris
```

Run `/doctor` inside IRIS to verify all configured keys are detected correctly.
