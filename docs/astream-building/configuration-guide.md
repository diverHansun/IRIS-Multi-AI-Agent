# Configuration Guide

Complete reference for Deep Agent streaming and safety configuration options.

## 1. Configuration Files

### providers.json

**Location:** `config/agents/deep/models/providers.json`

**Purpose:** Main agent model configuration including streaming, safety, and HITL settings.

**Structure:**
```json
{
  "provider_name": {
    "base_url": "https://api.example.com/v1",
    "api_key_env": "API_KEY_ENV_VAR",
    "description": "Provider description",
    "models": {
      "model_name": {
        // Basic LLM parameters
        "temperature": 0.6,
        "max_tokens": 4096,
        "context_window": 200000,
        "supports_tools": true,
        
        // Safety mechanisms
        "max_execution_time": 120,
        "max_recursion_limit": 50,
        "max_input_tokens": 100000,
        "max_output_tokens": 50000,
        
        // Streaming configuration
        "streaming_enabled": true,
        "stream_mode": "updates",
        "show_reasoning_steps": true,
        "show_tool_calls": true,
        "show_tool_results": true,
        "show_subagent_delegations": true,
        "show_elapsed_time": true,
        
        // HITL configuration
        "hitl_enabled": true,
        "hitl_config": {
          "dangerous_tools": ["delete_file", "execute_shell"],
          "tools": {
            "delete_file": {
              "allow_auto_approve": false,
              "warning_message": "This operation cannot be undone!"
            }
          }
        },
        
        // Middleware
        "middleware": {
          "filesystem": "default",
          "subagents": "default"
        }
      }
    }
  }
}
```

### subagents.json

**Location:** `config/agents/deep/models/subagents.json`

**Purpose:** Subagent model configuration (simpler than main agent).

**Structure:**
```json
{
  "subagent_type": {
    "providers": {
      "provider_name": {
        "base_url": "https://api.example.com/v1",
        "api_key_env": "API_KEY_ENV_VAR",
        "models": {
          "model_name": {
            "temperature": 0.6,
            "max_tokens": 4096,
            "context_window": 128000,
            "supports_tools": true,
            
            // Subagent-specific (simpler)
            "max_execution_time": 90,
            "max_recursion_limit": 30,
            "streaming_enabled": false,
            "hitl_enabled": false
          }
        }
      }
    }
  }
}
```

## 2. Configuration Options

### Basic LLM Parameters

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `temperature` | float | 0.6 | Sampling temperature (0-2) |
| `max_tokens` | int | 4096 | Maximum tokens per response |
| `context_window` | int | 200000 | Model context window size |
| `supports_tools` | bool | true | Whether model supports tool calling |

### Safety Mechanisms

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_execution_time` | int | 120 | Timeout in seconds |
| `max_recursion_limit` | int | 50 | Maximum reasoning steps |
| `max_input_tokens` | int | 100000 | Input token limit |
| `max_output_tokens` | int | 50000 | Output token limit |
| `max_cost_usd` | float | 1.0 | Maximum cost per query (optional) |

**Recommended values:**
- Main agent: `max_execution_time: 120`, `max_recursion_limit: 50`
- Subagents: `max_execution_time: 90`, `max_recursion_limit: 30`
- Basic agent: `max_execution_time: 60`, `max_recursion_limit: 15`

### Streaming Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `streaming_enabled` | bool | true | Enable streaming output |
| `stream_mode` | string | "updates" | LangGraph stream mode |
| `show_reasoning_steps` | bool | true | Display step counter |
| `show_tool_calls` | bool | true | Display tool invocations |
| `show_tool_results` | bool | true | Display tool results |
| `show_subagent_delegations` | bool | true | Display subagent calls |
| `show_elapsed_time` | bool | true | Display elapsed time |

**Stream modes:**
- `"updates"`: Node updates (recommended for Deep Agent)
- `"messages"`: Token-by-token output (for typing effect)
- `"values"`: Complete state after each step
- `"debug"`: Full debug information

### HITL Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `hitl_enabled` | bool | true | Enable Human-in-the-Loop |
| `dangerous_tools` | array | See below | Tools requiring approval |

**Default dangerous tools:**
```json
["delete_file", "execute_shell", "rm", "sudo", "chmod", "chown"]
```

**Tool-specific configuration:**
```json
{
  "tools": {
    "tool_name": {
      "allow_auto_approve": false,
      "warning_message": "Custom warning text"
    }
  }
}
```

## 3. Configuration Examples

### High-Security Configuration

**For production or sensitive operations:**
```json
{
  "claude-4.5-sonnet": {
    "max_execution_time": 60,
    "max_recursion_limit": 30,
    "max_input_tokens": 50000,
    "max_output_tokens": 20000,
    "max_cost_usd": 0.5,
    
    "streaming_enabled": true,
    "show_reasoning_steps": true,
    
    "hitl_enabled": true,
    "hitl_config": {
      "dangerous_tools": [
        "delete_file", "execute_shell", "rm", "sudo",
        "write_file", "edit_file", "chmod", "chown"
      ]
    }
  }
}
```

### Development Configuration

**For testing and experimentation:**
```json
{
  "claude-4.5-sonnet": {
    "max_execution_time": 300,
    "max_recursion_limit": 100,
    "max_input_tokens": 200000,
    "max_output_tokens": 100000,
    
    "streaming_enabled": true,
    "show_reasoning_steps": true,
    "show_tool_calls": true,
    "show_tool_results": true,
    
    "hitl_enabled": true,
    "hitl_config": {
      "dangerous_tools": ["delete_file", "execute_shell"]
    }
  }
}
```

### Minimal Display Configuration

**For clean output with less verbosity:**
```json
{
  "claude-4.5-sonnet": {
    "max_execution_time": 120,
    "max_recursion_limit": 50,
    
    "streaming_enabled": true,
    "show_reasoning_steps": false,
    "show_tool_calls": false,
    "show_tool_results": false,
    "show_subagent_delegations": true,
    "show_elapsed_time": false,
    
    "hitl_enabled": true
  }
}
```

### Subagent Configuration

**Subagents should be simpler:**
```json
{
  "research": {
    "providers": {
      "zhipu": {
        "models": {
          "glm-4.6": {
            "temperature": 0.6,
            "max_tokens": 4096,
            
            "max_execution_time": 90,
            "max_recursion_limit": 30,
            
            "streaming_enabled": false,
            "hitl_enabled": false
          }
        }
      }
    }
  }
}
```

## 4. Configuration Loading

### Priority Order

**From highest to lowest priority:**

1. **Runtime parameters** (code-level overrides)
2. **Model configuration** (providers.json)
3. **Default values** (hardcoded fallbacks)

### Runtime Override Example

```python
# Temporary override for specific query
config = {
    "max_execution_time": 300,  # 5 minutes for complex task
    "show_reasoning_steps": False  # Less verbose
}

result = await agent.ainvoke(query, **config)
```

### Loading Process

```python
# 1. Load from config file
model_config = load_config("config/agents/deep/models/providers.json")

# 2. Extract model settings
settings = model_config["anthropic"]["models"]["claude-4.5-sonnet"]

# 3. Apply defaults for missing values
timeout = settings.get("max_execution_time", 120)
recursion = settings.get("max_recursion_limit", 50)

# 4. Runtime override (if provided)
timeout = runtime_params.get("max_execution_time", timeout)
```

## 5. Validation Rules

### Required Fields

**Must be present in config:**
- `temperature`
- `max_tokens`
- `context_window`
- `supports_tools`

### Value Constraints

| Field | Constraint |
|-------|-----------|
| `temperature` | 0.0 ≤ value ≤ 2.0 |
| `max_tokens` | value > 0 |
| `max_execution_time` | value > 0 |
| `max_recursion_limit` | value > 0 |
| `stream_mode` | One of: "updates", "messages", "values", "debug" |

### Logical Constraints

- `max_output_tokens` ≤ `max_tokens`
- Subagent `max_execution_time` < Main agent `max_execution_time`
- Subagent `max_recursion_limit` < Main agent `max_recursion_limit`

## 6. Environment Variables

### API Keys

**Referenced in config:**
```json
{
  "api_key_env": "ANTHROPIC_API_KEY"
}
```

**Set in environment:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export TONGYI_API_KEY="sk-..."
export ZHIPU_API_KEY="..."
```

### Base URLs

**Optional override:**
```json
{
  "base_url": "https://api.openai-proxy.org/v1",
  "base_url_env": "ANTHROPIC_BASE_URL"  // Optional override
}
```

## 7. Configuration Management Commands

### View Current Configuration

```bash
# Show all settings for current model
/config show

# Show specific category
/config show safety
/config show streaming
/config show hitl
```

### Modify Configuration

```bash
# Temporarily adjust for current session
/config set max_execution_time 180
/config set show_tool_calls false

# Reset to defaults
/config reset
```

### Session-Specific Settings

```bash
# View HITL preferences
/session info

# Clear HITL auto-approvals
/session reset-hitl
```

## 8. Best Practices

### Production Deployment

1. **Set conservative limits:**
   - `max_execution_time: 60-120`
   - `max_recursion_limit: 30-50`
   - `max_cost_usd: 0.5-1.0`

2. **Enable all safety features:**
   - `hitl_enabled: true`
   - Comprehensive `dangerous_tools` list
   - Token monitoring enabled

3. **Moderate verbosity:**
   - `show_reasoning_steps: true`
   - `show_tool_calls: true`
   - `show_tool_results: false` (reduce noise)

### Development/Testing

1. **Relaxed limits:**
   - `max_execution_time: 300`
   - `max_recursion_limit: 100`

2. **Full visibility:**
   - All `show_*` options enabled
   - Detailed error messages

3. **Flexible HITL:**
   - Minimal `dangerous_tools` list
   - Easy to auto-approve for testing

### Performance Optimization

1. **Reduce display overhead:**
   - `show_tool_results: false`
   - `show_elapsed_time: false`

2. **Optimize limits:**
   - Set `max_recursion_limit` based on typical task complexity
   - Adjust `max_execution_time` per use case

3. **Subagent efficiency:**
   - Lower limits than main agent
   - Disable streaming for subagents

