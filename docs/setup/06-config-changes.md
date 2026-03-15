# 配置文件变更清单

## 1. 概述

本文档列出 Setup 模块实施过程中需要修改的所有配置文件，
包括模板文件、实际配置文件和代码中的默认值。

## 2. 变更一览

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `config.toml` 模板 | 修改 | 新增 `[setup]` 节 |
| `DEFAULT_CONFIG_TOML` | 修改 | 同步 `[setup]` 节 |
| `DEFAULT_ENV_TEMPLATE` | 修改 | 补全缺失变量，统一为唯一模板 |
| `.env.example`（项目根） | 修改 | 与 `DEFAULT_ENV_TEMPLATE` 同步 |
| `mainagents.example.json` | 修改 | anthropic 改为 openai（支持 base_url 覆写） |
| `mainagents.json`（bundled） | 修改 | 同上 |
| `subagents.example.json` | 修改 | 每个 subagent 加入 zhipu/tongyi/openai 三个 provider |
| `subagents.json`（bundled） | 修改 | 同上 |
| `basic/providers.json` | 修改 | 新增 tongyi provider |
| `mcp.example.toml` | 修改 | 去除 filesystem，修正占位符 |
| `DEFAULT_CONFIG` (defaults.py) | 修改 | `deep_agent.default_provider` 改为 zhipu |

## 3. config.toml 变更

### 3.1 新增 [setup] 节

在 `DEFAULT_CONFIG_TOML`（`src/core/config/defaults.py`）末尾追加：

```toml
# =============================================================================
# Setup Wizard State (managed automatically, do not edit manually)
# =============================================================================

[setup]
completed = false
completed_at = ""
version = ""
```

### 3.2 DEFAULT_CONFIG 变更

```python
DEFAULT_CONFIG: Dict[str, Any] = {
    ...
    "deep_agent": {
        "default_provider": "zhipu",           # was "anthropic"
        "default_model": "glm-4.6",            # was "claude-4.5-sonnet"
        ...
    },
    "setup": {
        "completed": False,
        "completed_at": "",
        "version": "",
    },
}
```

## 4. .env 模板统一

### 4.1 问题

当前存在两份不同步的 .env 模板：
- 项目根 `.env.example`：包含 DIFY, AMAP_MAPS, NOTION_MCP_URL，提到 UTF-16 编码
- `DEFAULT_ENV_TEMPLATE`（defaults.py）：更精简，缺少 Dify/MCP 变量

### 4.2 方案

`DEFAULT_ENV_TEMPLATE` 作为唯一权威模板，项目根 `.env.example` 同步更新。

### 4.3 统一后的 DEFAULT_ENV_TEMPLATE

```python
DEFAULT_ENV_TEMPLATE = '''# IRIS Global Environment Variables
# This file is loaded automatically when running iris from any directory.
# Copy this file to .env and fill in your API keys.

# =============================================================================
# LLM Providers (at least one is required)
# =============================================================================
ZHIPU_API_KEY=your_zhipu_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
TONGYI_API_KEY=your_tongyi_api_key_here

# OpenAI-compatible API (optional, for custom endpoints / proxy)
# OPENAI_BASE_URL=https://api.openai.com/v1

# =============================================================================
# Default LLM Settings
# =============================================================================
DEFAULT_LLM_PROVIDER=zhipu
DEFAULT_LLM_MODEL=glm-4.5-flash

# =============================================================================
# Tool Services (optional, skip if not needed)
# =============================================================================
TAVILY_API_KEY=your_tavily_api_key_here
AMAP_API_KEY=your_amap_api_key_here

# =============================================================================
# MCP Services (optional, skip if not needed)
# =============================================================================
NOTION_TOKEN=your_notion_token_here
CONTEXT7_API_KEY=your_context7_api_key_here
AMAP_MAPS_API_KEY=your_amap_maps_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_api_key_here

# =============================================================================
# Dify Engine (optional, skip if not needed)
# =============================================================================
DIFY_API_KEY=your_dify_api_key_here
DIFY_BASE_URL=https://api.dify.ai/v1

# =============================================================================
# Ollama (local models, optional)
# =============================================================================
# OLLAMA_BASE_URL=http://localhost:11434
'''
```

### 4.4 项目根 .env.example 同步

项目根的 `.env.example` 内容与上述模板保持一致。
去除 UTF-16 编码说明（统一使用 UTF-8）。

## 5. mainagents 配置变更

### 5.1 变更内容

将 `anthropic` provider 替换为 `openai` provider，支持 `base_url` 覆写。

### 5.2 变更前（anthropic）

以下为 bundled example 模板中的标准值。注意：实际部署的 `~/.iris/agents/deep/mainagents.json`
可能包含用户自定义值（如代理 base_url、自定义 model 名称），这些文件不会被自动覆盖。

```json
{
  "anthropic": {
    "description": "Anthropic Claude models configured for deep agents",
    "default_model": "claude-4.5-sonnet",
    "api_config": {
      "base_url": "https://api.anthropic.com/v1",
      "api_key_env": "ANTHROPIC_API_KEY"
    },
    "models": { ... }
  }
}
```

**已知问题**：当前实际的 bundled `mainagents.json` 中 anthropic 条目使用了代理地址
（`zenmux.ai`）和非标准 API key 环境变量名（`ZENMUX_API_KEY`），model 名称为
`claude-sonnet-4-6`。这些偏差在替换为 openai provider 时将一并修正。

### 5.3 变更后（openai）

```json
{
  "openai": {
    "description": "OpenAI-compatible models for deep agents (supports custom base_url)",
    "default_model": "gpt-4o",
    "api_config": {
      "base_url": "https://api.openai.com/v1",
      "base_url_env": "OPENAI_BASE_URL",
      "api_key_env": "OPENAI_API_KEY"
    },
    "models": {
      "gpt-4o": {
        "llm_params": {
          "temperature": 0.6,
          "max_tokens": 4096,
          "streaming": false
        },
        "runtime_config": {
          "recursion_limit": 300,
          "step_timeout": 300,
          "stream_mode": "updates"
        },
        "middleware_config": {
          "filesystem": "default",
          "subagents": "default",
          "shell": "default"
        },
        "display_config": {
          "streaming_enabled": true,
          "show_reasoning_steps": true,
          "show_tool_calls": true,
          "show_tool_results": true,
          "show_subagent_delegations": true,
          "show_elapsed_time": true
        },
        "safety_config": {
          "max_execution_time": 900,
          "hitl_config": {
            "dangerous_tools": ["shell", "write_real_file", "edit_real_file"],
            "tools": {
              "write_real_file": {
                "allow_auto_approve": false,
                "warning_message": "Writing to the host filesystem can overwrite important source files."
              },
              "edit_real_file": {
                "allow_auto_approve": false,
                "warning_message": "Editing host files modifies source code or configuration."
              },
              "shell": {
                "allow_auto_approve": false,
                "warning_message": "Shell commands can change or destroy host data."
              }
            }
          }
        },
        "metadata": {
          "context_window": 128000,
          "supports_tools": true,
          "max_input_tokens": 100000,
          "max_output_tokens": 16384
        }
      }
    }
  }
}
```

保留 `tongyi` 和 `zhipu` provider 不变。

### 5.4 影响的文件

| 文件 | 路径 |
|------|------|
| bundled example | `config/agents/deep/mainagents.example.json` |
| bundled actual | `config/agents/deep/mainagents.json` |
| legacy bundled | `config/agents/deep/models/mainagents.json` |
| legacy bundled example | `config/agents/deep/models/mainagents.example.json` |

注意：用户级 `~/.iris/agents/deep/mainagents.json` 不自动更新。
用户需要手动运行 `/iris setup --agent deep` 或重置配置。

## 6. subagents 配置变更

### 6.1 变更内容

每个 subagent（research/coding/analysis）扩展为多 provider 结构，
系统运行时根据已配置的 API key 自动选择可用 provider。

去除 anthropic provider，保留 zhipu、tongyi、openai。

### 6.2 变更后结构

```json
{
  "research": {
    "name": "research",
    "description": "Research specialist for deep information gathering",
    "providers": {
      "zhipu": {
        "model": "glm-4.5-flash",
        "api_config": {
          "base_url": "https://open.bigmodel.cn/api/paas/v4",
          "api_key_env": "ZHIPU_API_KEY"
        },
        "model_params": {
          "temperature": 0.6,
          "max_tokens": 4096,
          "streaming": false
        }
      },
      "tongyi": {
        "model": "qwen3.5-plus",
        "api_config": {
          "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
          "api_key_env": "TONGYI_API_KEY"
        },
        "model_params": {
          "temperature": 0.6,
          "max_tokens": 4096,
          "streaming": false
        }
      },
      "openai": {
        "model": "gpt-4o-mini",
        "api_config": {
          "base_url": "https://api.openai.com/v1",
          "base_url_env": "OPENAI_BASE_URL",
          "api_key_env": "OPENAI_API_KEY"
        },
        "model_params": {
          "temperature": 0.6,
          "max_tokens": 4096,
          "streaming": false
        }
      }
    },
    "agent_config": {
      "tools": [],
      "middleware": [],
      "checkpointer": false
    },
    "runtime_limits": {
      "max_execution_time": 90,
      "step_timeout": 30,
      "recursion_limit": 60
    },
    "display_config": {
      "streaming_enabled": false,
      "show_reasoning_steps": false,
      "show_tool_calls": false
    },
    "metadata": {
      "context_window": 128000,
      "supports_tools": true
    }
  }
}
```

注意：原有 `llm_config` 单一 provider 结构改为 `providers` 多 provider 结构。
这是一个 **breaking change**。

**迁移约束：配置文件变更与注册代码变更必须在同一个 release 中发布。**

具体要求：
1. `SubAgentsProviderRegistry` 的 `_extract_llm_config()` 方法需要同步修改，
   支持新的 `providers` 结构。
2. 添加格式检测兼容层：检测 `llm_config`（旧格式）或 `providers`（新格式），
   统一输出为标准化的 provider config dict。
3. 对已有 `~/.iris/agents/deep/subagents.json`（旧格式）的用户，
   `ConfigInitializer.sync_missing` 不会覆盖已存在的文件。
   需要添加格式版本检测逻辑：如果检测到旧格式，打印迁移提示并提供
   `/iris setup --agent deep` 命令引导用户更新。

**兼容层示例：**

```python
def _normalize_subagent_config(raw: dict) -> dict:
    """Support both old (llm_config) and new (providers) format."""
    if "providers" in raw:
        return raw  # new format
    if "llm_config" in raw:
        # convert old single-provider to new multi-provider
        llm = raw["llm_config"]
        provider_name = llm.get("provider", "unknown")
        return {
            **raw,
            "providers": {
                provider_name: {
                    "model": llm.get("model"),
                    "api_config": llm.get("api_config", {}),
                    "model_params": llm.get("model_params", {}),
                }
            },
        }
    return raw
```

**已知问题**：当前实际的 `subagents.json` 中存在以下偏差：
- `analysis` subagent 的 `api_key_env` 有拼写错误（`ZENMUX_API_LEY` 应为 `ZENMUX_API_KEY`）
- 部分 subagent 声明 `provider: "tongyi"` 但实际 `base_url` 指向代理地址（`zenmux.ai`）

兼容层执行 best-effort 转换，不校验 provider 标签与 base_url 的语义一致性。
这些偏差在替换为新的多 provider 结构时将一并修正。

### 6.3 自动选择逻辑（后续实现）

运行时的 provider 选择逻辑（将在注册机制调整时实现）：

```python
def resolve_subagent_provider(subagent_config: dict) -> dict:
    """Select first provider with available API key."""
    providers = subagent_config.get("providers", {})
    for provider_name, provider_config in providers.items():
        api_key_env = provider_config["api_config"]["api_key_env"]
        if os.getenv(api_key_env):
            return {"provider": provider_name, **provider_config}
    raise ConfigurationError("No provider with valid API key found for subagent")
```

### 6.4 影响的文件

| 文件 | 路径 |
|------|------|
| bundled example | `config/agents/deep/subagents.example.json` |
| bundled actual | `config/agents/deep/subagents.json` |
| legacy bundled | `config/agents/deep/models/subagents.json` |
| legacy bundled example | `config/agents/deep/models/subagents.example.json` |

## 7. basic/providers.json 变更

### 7.1 变更内容

新增 `tongyi` provider。

### 7.2 新增内容

```json
{
  "providers": {
    "zhipu": { ... },
    "openai": { ... },
    "tongyi": {
      "name": "Tongyi Qwen",
      "api_key_env": "TONGYI_API_KEY",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "base_url_env": "TONGYI_BASE_URL",
      "default_model": "qwen3-max",
      "models": {
        "qwen3-max": {
          "name": "Qwen3 Max",
          "description": "Full-featured Qwen model",
          "temperature": 0.6,
          "max_tokens": 4096,
          "context_window": 128000,
          "supports_tools": true,
          "streaming": true
        },
        "qwen3-coder-plus": {
          "name": "Qwen3 Coder Plus",
          "description": "Code-optimized Qwen model",
          "temperature": 0.6,
          "max_tokens": 8192,
          "context_window": 128000,
          "supports_tools": true,
          "streaming": true
        }
      }
    }
  }
}
```

### 7.3 影响的文件

| 文件 | 路径 |
|------|------|
| bundled | `config/agents/basic/models/providers.json` |
| bundled (legacy) | `config/agents/basic/providers.json` (if exists) |

## 8. mcp.example.toml 变更

### 8.1 变更内容

- 去除 filesystem MCP server
- 修正占位符，使用实际合理的示例值

### 8.2 变更后

```toml
# IRIS MCP Server Configuration
# Copy to ~/.iris/tools/mcp/mcp.toml and configure as needed.

enabled = true
auto_start = true
prefer_mcp = true
namespace_strategy = "prefix"
default_prefix = "mcp_"

# Notion MCP
[mcp_servers.notion]
transport = "stdio"
command = "npx"
args = ["-y", "@notionhq/notion-mcp-server"]
rename_prefix = "notion:"

[mcp_servers.notion.env]
NOTION_TOKEN = "$NOTION_TOKEN"

# Context7 MCP
[mcp_servers.context7]
transport = "stdio"
command = "npx"
args = ["-y", "@upstash/context7-mcp", "--transport", "stdio"]
rename_prefix = "ctx7:"

[mcp_servers.context7.env]
CONTEXT7_API_KEY = "$CONTEXT7_API_KEY"

# AMap Maps MCP
[mcp_servers.amap-maps]
transport = "stdio"
command = "npx"
args = ["-y", "@amap/amap-maps-mcp-server"]
rename_prefix = "amap:"

[mcp_servers.amap-maps.env]
AMAP_MAPS_API_KEY = "$AMAP_MAPS_API_KEY"

# Firecrawl MCP
[mcp_servers.firecrawl-mcp]
transport = "stdio"
command = "npx"
args = ["-y", "firecrawl-mcp"]
rename_prefix = "firecrawl:"

[mcp_servers.firecrawl-mcp.env]
FIRECRAWL_API_KEY = "$FIRECRAWL_API_KEY"

# Chrome DevTools MCP
[mcp_servers.chrome-devtools]
transport = "stdio"
command = "npx"
args = ["-y", "chrome-devtools-mcp@latest"]
rename_prefix = "chrome:"
```

## 9. defaults.py DEFAULT_CONFIG 变更

```python
DEFAULT_CONFIG: Dict[str, Any] = {
    ...
    "deep_agent": {
        "default_provider": "zhipu",         # changed from "anthropic"
        "default_model": "glm-4.6",          # changed from "claude-4.5-sonnet"
        "max_execution_time": 900,
        "recursion_limit": 300,
    },
    "setup": {                               # new section
        "completed": False,
        "completed_at": "",
        "version": "",
    },
}
```

## 10. 变更影响矩阵

| 变更 | 影响模块 | 需要代码修改 | 优先级 |
|------|---------|-------------|--------|
| config.toml [setup] | initializer, wizard | 是（wizard 读写） | P0 |
| DEFAULT_ENV_TEMPLATE 统一 | defaults.py, .env.example | 是（模板替换） | P0 |
| mainagents anthropic->openai | deep agent lifecycle, registry | 是（后续联动） | P1 |
| subagents 多 provider | subagents registry, deep runtime | 是（后续联动） | P1 |
| basic providers +tongyi | basic agent registry | 是（后续联动） | P1 |
| mcp.example.toml | initializer copy | 否（纯文件替换） | P0 |
| DEFAULT_CONFIG deep_agent | defaults.py | 是（值修改） | P0 |

P0 项在 setup 模块实施时同步完成。
P1 项属于"验证/注册机制调整"，在 setup 模块完成后单独实施。

## 11. ANTHROPIC_API_KEY 保留策略

虽然 setup 向导不再引导配置 Anthropic provider，但以下位置保留 `ANTHROPIC_API_KEY`：

| 位置 | 处理方式 |
|------|---------|
| `DEFAULT_ENV_TEMPLATE` | 移除（不在模板中引导） |
| `config.toml` 模板 `[api_keys]` | 保留 `anthropic_api_key = "${ANTHROPIC_API_KEY}"` |
| `Settings` 类 | 保留 `has_anthropic()` / `get_api_key("anthropic")` |
| `IrisConfig.APIKeysConfig` | 保留 `anthropic_api_key` 字段 |

理由：用户如果手动在 `.env` 中添加了 `ANTHROPIC_API_KEY`，系统应能正常识别和使用。
移除的只是 setup 向导中的引导入口，不是功能支持。

## 12. EnvWriter 错误处理规格

`EnvWriter` 需要处理以下异常场景：

| 场景 | 处理方式 |
|------|---------|
| `.env` 文件不存在 | 创建新文件（从 `.env.example` 复制或创建空文件） |
| `.env` 文件只读 | 捕获 `PermissionError`，输出提示信息并指导用户手动修改 |
| `.env` 文件编码异常 | 尝试 UTF-8/GBK/UTF-16 多编码读取（复用 `env_loader.py` 的逻辑） |
| 写入后文件权限 | 不主动修改权限（Windows 环境无 POSIX 权限模型） |
| 并发写入 | 不做锁机制（单用户 CLI 工具，并发写入概率极低，属于已知限制） |

```python
class EnvWriter:
    def write_key(self, key: str, value: str) -> None:
        try:
            ...  # read, update, write
        except PermissionError:
            raise SetupError(
                f"Cannot write to {self.env_path}. "
                f"Please check file permissions or edit manually."
            )
```

## 13. mainagents.json 实际值说明

文档中 mainagents.json 的"变更前"描述使用的是 example 模板中的标准值，
不是用户自定义后的实际值。实际部署的 `~/.iris/agents/deep/mainagents.json`
可能包含用户自定义的 base_url、model 名称和参数，这些文件不会被 setup 自动覆盖。

setup 向导只操作 `.env`（API key 和环境变量），不直接修改用户级 JSON 配置文件。
JSON 配置文件的更新通过以下方式进行：
- 新安装：`ConfigInitializer` 从 bundled config 复制模板
- 已安装：用户手动编辑或通过版本升级提示后运行 `/iris setup`

## 14. 后续联动修复项（验证/注册机制调整阶段）

以下问题不在 setup 模块范围内，但在实施过程中发现，需要在后续阶段处理：

1. **`_validate_config()` 缺少 tongyi 检查**：`settings.py` 的启动验证只检查 zhipu/openai/anthropic，
   未包含 tongyi。setup 向导将 tongyi 作为一级 provider 推荐，验证逻辑需同步更新。

2. **`has_notion()` 误判**：`Settings.has_notion()` 拒绝以 `secret_` 开头的 token，
   但真实的 Notion Integration Token 格式为 `secret_xxx`（见 `.env.example` 示例）。
   这会导致 doctor 输出 false negative。需要修改 `has_notion()` 的占位符检测逻辑，
   区分真实 token（`secret_` + 有效字符）与占位符（`secret_your_*`）。

3. **`DEFAULT_CONFIG` 中 `deep_agent.default_model` 值**：当前为 `"claude-4.5-sonnet"`，
   需改为 `"glm-4.6"` 以与 `default_provider: "zhipu"` 对应。
