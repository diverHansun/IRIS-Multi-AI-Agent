# JSON 配置结构变更

## 1. 概述

本文档定义 provider 配置 JSON 文件的结构变更，核心变更是新增 `adapter` 字段，
使 registry 能够根据配置自动选择正确的适配器，支持用户动态增删 provider/model。

## 2. LLM providers.json 变更

### 2.1 变更内容

文件路径：`config/llm/models/providers.json`

| 变更项 | 变更前 | 变更后 |
|--------|--------|--------|
| provider key | UPPERCASE (`"ZHIPU"`) | lowercase (`"zhipu"`) |
| `adapter` 字段 | 无 | 新增，声明适配器类型 |
| tongyi provider | 无 | 新增 |

### 2.2 变更后完整结构

```json
{
  "schema_version": "2.0",
  "description": "LLM provider configuration with adapter routing",
  "providers": {
    "zhipu": {
      "adapter": "zhipu",
      "name": "Zhipu AI",
      "api_key_env": "ZHIPU_API_KEY",
      "base_url": null,
      "base_url_env": null,
      "default_model": "glm-4.5-flash",
      "models": {
        "glm-4-plus": {
          "name": "GLM-4-Plus",
          "description": "Zhipu AI flagship model with comprehensive capabilities",
          "temperature": 0.2,
          "max_tokens": 2048,
          "context_window": 128000,
          "supports_tools": true,
          "streaming": true
        },
        "glm-4.5": {
          "name": "GLM-4.5",
          "description": "Next-gen MoE architecture model with 128K context",
          "temperature": 0.1,
          "max_tokens": 8192,
          "context_window": 128000,
          "supports_tools": true,
          "streaming": true,
          "thinking_mode": true
        },
        "glm-4.5-flash": {
          "name": "GLM-4.5-Flash",
          "description": "Free lightning version with 128K context",
          "temperature": 0.5,
          "max_tokens": 96000,
          "context_window": 128000,
          "supports_tools": true,
          "streaming": true,
          "thinking_mode": true
        }
      }
    },
    "openai": {
      "adapter": "openai",
      "name": "OpenAI",
      "api_key_env": "OPENAI_API_KEY",
      "base_url": "https://api.openai.com/v1",
      "base_url_env": "OPENAI_BASE_URL",
      "default_model": "gpt-4o-mini",
      "models": {
        "gpt-5": { "..." : "..." },
        "gpt-5-mini": { "..." : "..." },
        "gpt-4o": { "..." : "..." },
        "gpt-4o-mini": { "..." : "..." },
        "gpt-4.1-nano": { "..." : "..." }
      }
    },
    "tongyi": {
      "adapter": "openai",
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
    },
    "ollama": {
      "adapter": "ollama",
      "name": "Ollama Local Models",
      "api_key_env": null,
      "base_url": "http://localhost:11434",
      "base_url_env": "OLLAMA_BASE_URL",
      "default_model": "auto",
      "extra_params": {
        "timeout": 60,
        "keep_alive": "5m"
      },
      "models": {
        "auto": {
          "name": "Auto-detect Model",
          "description": "Automatically detect and use available local model",
          "temperature": 0.1,
          "max_tokens": 4096,
          "context_window": 8192,
          "supports_tools": true,
          "streaming": true
        }
      }
    }
  }
}
```

### 2.3 schema_version 升级

从 `"1.0"` 升级到 `"2.0"`，标识配置格式变更。
registry 加载时可以通过 schema_version 判断是否需要兼容处理。

## 3. BasicAgents providers.json 变更

### 3.1 变更内容

文件路径：`config/agents/basic/models/providers.json`

| 变更项 | 变更前 | 变更后 |
|--------|--------|--------|
| `adapter` 字段 | 无 | 新增 |
| tongyi provider | 无 | 新增 |

### 3.2 变更后结构（关键部分）

```json
{
  "schema_version": "2.0",
  "description": "BasicAgents provider configuration with adapter routing",
  "providers": {
    "zhipu": {
      "adapter": "zhipu",
      "name": "Zhipu AI",
      "api_key_env": "ZHIPU_API_KEY",
      "base_url": null,
      "base_url_env": null,
      "default_model": "glm-4.5-flash",
      "models": {
        "glm-4-plus": { "...": "..." },
        "glm-4.5": { "...": "..." },
        "glm-4.5-flash": { "...": "..." }
      }
    },
    "openai": {
      "adapter": "openai",
      "name": "OpenAI",
      "api_key_env": "OPENAI_API_KEY",
      "base_url": "https://api.openai.com/v1",
      "base_url_env": "OPENAI_BASE_URL",
      "default_model": "gpt-4o-mini",
      "models": { "...": "..." }
    },
    "tongyi": {
      "adapter": "openai",
      "name": "Tongyi Qwen",
      "api_key_env": "TONGYI_API_KEY",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "base_url_env": "TONGYI_BASE_URL",
      "default_model": "qwen3-max",
      "models": {
        "qwen3-max": {
          "name": "Qwen3 Max",
          "description": "Full-featured Qwen model",
          "agent_type": "function_calling",
          "temperature": 0.6,
          "max_tokens": 4096,
          "context_window": 128000,
          "max_iterations": 10,
          "max_execution_time": 300,
          "memory_enabled": true,
          "supports_tools": true,
          "streaming": false
        },
        "qwen3-coder-plus": {
          "name": "Qwen3 Coder Plus",
          "description": "Code-optimized Qwen model",
          "agent_type": "function_calling",
          "temperature": 0.6,
          "max_tokens": 8192,
          "context_window": 128000,
          "max_iterations": 10,
          "max_execution_time": 300,
          "memory_enabled": true,
          "supports_tools": true,
          "streaming": false
        }
      }
    }
  }
}
```

注意：BasicAgents 的 model 配置比 LLM 多了 `agent_type`、`max_iterations`、
`max_execution_time`、`memory_enabled` 等 agent 运行时参数。
tongyi 的这些参数参照现有 openai provider 的配置。

## 4. `adapter` 字段兼容性

### 4.1 旧配置缺失 adapter 字段

用户可能使用旧版本配置文件（无 `adapter` 字段）。
registry 在读取时需要 fallback 推断：

```python
def _resolve_adapter_type(self, provider_name: str, config: dict) -> str:
    """Resolve adapter type from config, with fallback for old format."""
    adapter = config.get("adapter")
    if adapter:
        return adapter

    # Fallback: infer from provider name (backward compatibility)
    known_adapters = {"zhipu": "zhipu", "ollama": "ollama"}
    return known_adapters.get(provider_name, "openai")
```

逻辑：
- 有 `adapter` 字段 -> 直接使用
- 无 `adapter` 字段 -> 已知的 zhipu/ollama 使用专用 adapter，其他默认 `"openai"`

### 4.2 schema_version 检测

```python
def _load_from_config(self) -> None:
    ...
    schema_version = config_data.get("schema_version", "1.0")
    if schema_version < "2.0":
        logger.info(
            "Legacy config format (schema_version=%s), "
            "adapter field will be inferred",
            schema_version,
        )
```

## 5. 用户动态增删 Provider

### 5.1 添加新 Provider

用户在 `~/.iris/llm/providers.json` 中添加即可：

```json
{
  "providers": {
    "deepseek": {
      "adapter": "openai",
      "name": "DeepSeek",
      "api_key_env": "DEEPSEEK_API_KEY",
      "base_url": "https://api.deepseek.com/v1",
      "base_url_env": "DEEPSEEK_BASE_URL",
      "default_model": "deepseek-chat",
      "models": {
        "deepseek-chat": {
          "name": "DeepSeek Chat",
          "description": "DeepSeek general chat model",
          "temperature": 0.7,
          "max_tokens": 4096,
          "context_window": 128000,
          "supports_tools": true,
          "streaming": true
        }
      }
    }
  }
}
```

同时在 `~/.iris/.env` 中添加：

```
DEEPSEEK_API_KEY=your_actual_key
```

三层配置合并机制（built-in < user < project）会自动将新 provider 加入 registry。

### 5.2 添加新 Model

在已有 provider 的 `models` 节中添加即可：

```json
{
  "providers": {
    "zhipu": {
      "models": {
        "glm-5": {
          "name": "GLM-5",
          "description": "Next generation model",
          "temperature": 0.3,
          "max_tokens": 8192,
          "context_window": 256000,
          "supports_tools": true,
          "streaming": true
        }
      }
    }
  }
}
```

用户级配置中只需要写增量部分，`_deep_merge()` 会与 built-in 配置合并。

### 5.3 删除/禁用 Provider

在用户级配置中将 provider 的 `models` 设为空对象即可使其不可用：

```json
{
  "providers": {
    "ollama": {
      "models": {}
    }
  }
}
```

或者不在用户级配置中引用该 provider（默认只有 built-in 配置提供）。

注意：当前的 `_deep_merge()` 是追加合并，不支持删除 built-in 配置中的 provider。
如果用户需要完全移除某个 built-in provider，可以在用户级配置中覆盖为空模型列表。

## 6. Deep/SubAgents 配置 -- 不在本文档范围

Deep 模式和 SubAgent 的配置结构变更（如 subagents 多 provider 结构）
已在 `docs/setup/06-config-changes.md` 中定义。

本重构不影响 Deep/SubAgent 的 registry 代码，因为：
- `DeepAgentsProviderRegistry` 通过 `init_chat_model()` 创建 LLM，不需要 adapter 映射
- `SubAgentsProviderRegistry` 同理

## 7. adapter 字段的完整规格

### 7.1 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `adapter` | `string` | 推荐 | 按 provider name 推断 | 适配器类型，决定使用哪个 Adapter/Instance 类 |

### 7.2 有效值

| 值 | LLM Adapter | Agent Adapter | 适用场景 |
|----|------------|---------------|---------|
| `"zhipu"` | `ZhipuAdapter` + `ZhipuAILLM` | `ZhipuAgentAdapter` | 智谱 AI 官方 SDK |
| `"openai"` | `OpenAIAdapter` + `OpenAILLM` | `OpenAIAgentAdapter` | OpenAI 及所有 OpenAI-compatible API |
| `"ollama"` | `OllamaAdapter` + `OllamaLLM` | (不适用) | 本地 Ollama 服务 |

### 7.3 扩展新 adapter 类型

如果未来需要新的 adapter 类型（如 `"google"` 用于 Gemini），步骤：

1. 实现新的 Adapter 类（如 `GeminiAdapter`）和 Instance 类（如 `GeminiLLM`）
2. 在 `ADAPTER_REGISTRY` 中注册：`"google": (GeminiAdapter, GeminiLLM)`
3. 在 JSON 配置中使用：`"adapter": "google"`

这是唯一需要修改代码的场景。对于所有 OpenAI-compatible API，直接复用
`adapter: "openai"` 即可，无需新增适配器。
